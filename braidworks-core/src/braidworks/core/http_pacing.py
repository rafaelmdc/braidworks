"""Request-level pacing without a required HTTP client or broker dependency."""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from threading import Lock
from time import monotonic
from typing import Any

from braidworks.core.exceptions import BackendConfigurationError

RequestBudget = Callable[[str, str], Awaitable[None]]
_budget: ContextVar[RequestBudget | None] = ContextVar("braidworks_request_budget", default=None)
_target: ContextVar[tuple[str, str] | None] = ContextVar("braidworks_http_target", default=None)


def parse_rate_limits(spec: str | None) -> dict[str, float]:
    limits = {}
    for entry in (spec or "").split(","):
        if not entry.strip() or "=" not in entry:
            continue
        target, _, value = entry.strip().partition("=")
        try:
            rate = float(value)
        except ValueError:
            continue
        if not target.strip() or not math.isfinite(rate) or rate <= 0:
            raise ValueError(f"invalid rate limit: {entry}")
        limits[target.strip()] = rate
    return limits


def rate_for(limits: dict[str, float], weaver_id: str, backend: str) -> float | None:
    return limits.get(f"{weaver_id}:{backend}", limits.get(weaver_id))


def validate_request_pacing(weaver: Any, backend: str) -> None:
    try:
        rate = rate_for(
            parse_rate_limits(os.environ.get("BRAIDWORKS_RATE_LIMITS")),
            weaver.MANIFEST.weaver_id,
            backend,
        )
    except ValueError as exc:
        raise BackendConfigurationError(str(exc)) from exc
    if rate is not None and not weaver.supports_request_pacing(backend):
        raise BackendConfigurationError(
            f"{weaver.MANIFEST.weaver_id}:{backend} does not declare request pacing support"
        )


@contextmanager
def request_budget(budget: RequestBudget) -> Iterator[None]:
    """Install an async budget callback for this task and its children; restore on exit."""
    token = _budget.set(budget)
    try:
        yield
    finally:
        _budget.reset(token)


class _LocalBucket:
    def __init__(self, rate: float, now: float):
        self.rate = rate
        self.tokens = 1.0
        self.updated = now

    async def acquire(self, rate: float) -> None:
        while True:
            with _local_lock:
                now = monotonic()
                self.tokens = min(1.0, self.tokens + max(0, now - self.updated) * self.rate)
                self.updated = now
                self.rate = rate
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                delay = min((1 - self.tokens) / self.rate, 0.5)
            await asyncio.sleep(delay)


_local: dict[tuple[str, str], _LocalBucket] = {}
_local_lock = Lock()


async def _pace_request(request: Any) -> None:
    target = _target.get()
    if target is None:
        return
    budget = _budget.get()
    if budget is not None:
        await budget(*target)
        return
    try:
        limits = parse_rate_limits(os.environ.get("BRAIDWORKS_RATE_LIMITS"))
    except ValueError as exc:
        raise BackendConfigurationError(str(exc)) from exc
    rate = rate_for(limits, *target)
    if rate is None:
        return
    with _local_lock:
        bucket = _local.setdefault(target, _LocalBucket(rate, monotonic()))
    await bucket.acquire(rate)


class PacedHTTPClient:
    """Delegate to an async client, tagging each request for its shared pacing hook.

    Redirects and authentication round trips invoke the client's request hook again.
    Connections, existing hooks, transports and ownership remain with the original
    client. Reusing one injected client across different weavers does not double-charge.
    """

    def __init__(self, client: Any, weaver_id: str, backend: str = "api"):
        self._client = client
        self._target = (weaver_id, backend)
        hooks = client.event_hooks.setdefault("request", [])
        if _pace_request not in hooks:
            hooks.append(_pace_request)

    def __getattr__(self, name: str) -> Any:
        operation = getattr(self._client, name)
        if name not in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
            "request",
            "send",
        }:
            return operation

        async def paced(*args, **kwargs):
            token = _target.set(self._target)
            try:
                return await operation(*args, **kwargs)
            finally:
                _target.reset(token)

        return paced

    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        token = _target.set(self._target)
        try:
            async with self._client.stream(*args, **kwargs) as response:
                yield response
        finally:
            _target.reset(token)
