"""GMrepo acquisition policy shared by summary and profile stages."""

from __future__ import annotations

import math
import time
import urllib.error
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class AcquisitionPolicy:
    """Bounds for one complete build; every attempt counts against ``max_calls``."""

    workers: int = 4
    requests_per_second: float = 2.0
    max_attempts: int = 3
    max_calls: int = 10000
    retry_backoff: float = 1.0
    max_retry_delay: float = 60.0

    def __post_init__(self) -> None:
        for key in ("workers", "max_attempts", "max_calls"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{key} must be a positive integer")
        for key in ("requests_per_second", "retry_backoff", "max_retry_delay"):
            value = getattr(self, key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"{key} must be finite")
            if value < 0 or (key == "requests_per_second" and value == 0):
                raise ValueError(f"{key} has an invalid acquisition limit")

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> AcquisitionPolicy:
        return cls(**data)


class _CallBudgetExceeded(urllib.error.URLError):
    """An incomplete acquisition, never evidence of source absence."""


class _AcquisitionClient:
    """Thread-safe admission and retry around an injectable synchronous POST."""

    def __init__(
        self,
        post: Callable[[str, dict[str, Any]], Any],
        policy: AcquisitionPolicy,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.post = post
        self.policy = policy
        self.clock = clock
        self.sleep = sleep
        self.lock = Lock()
        self.next_start = 0.0
        self.calls = 0
        self.retries = 0
        self.budget_exhausted = False

    def _admit(self, *, retry: bool = False) -> None:
        # Hold the lock while waiting so admission cannot reorder or burst after a delay.
        with self.lock:
            if self.calls >= self.policy.max_calls:
                self.budget_exhausted = True
                raise _CallBudgetExceeded(
                    f"acquisition call budget exhausted ({self.policy.max_calls})"
                )
            delay = max(0.0, self.next_start - self.clock())
            if delay:
                self.sleep(delay)
            self.next_start = self.clock() + 1 / self.policy.requests_per_second
            self.calls += 1
            if retry:
                self.retries += 1

    def __call__(self, endpoint: str, body: dict[str, Any]) -> Any:
        for attempt in range(self.policy.max_attempts):
            self._admit(retry=attempt > 0)
            try:
                return self.post(endpoint, body)
            except (urllib.error.URLError, TimeoutError) as exc:
                if isinstance(exc, _CallBudgetExceeded):
                    raise
                if isinstance(exc, urllib.error.HTTPError) and exc.code not in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
                if attempt + 1 >= self.policy.max_attempts:
                    raise
                delay = min(self.policy.retry_backoff * 2**attempt, self.policy.max_retry_delay)
                if isinstance(exc, urllib.error.HTTPError) and exc.headers:
                    retry_after = exc.headers.get("Retry-After")
                    if retry_after:
                        try:
                            requested = float(retry_after)
                        except ValueError:
                            try:
                                requested = (
                                    parsedate_to_datetime(retry_after).timestamp() - time.time()
                                )
                            except (ValueError, TypeError, OverflowError):
                                requested = 0.0
                        if math.isfinite(requested) and requested > 0:
                            if requested > self.policy.max_retry_delay:
                                # Do not violate a provider delay to fit our waiting budget.
                                raise
                            delay = max(delay, requested)
                with self.lock:
                    self.next_start = max(self.next_start, self.clock() + delay)
        raise AssertionError("unreachable acquisition retry")

    def coverage(self) -> dict[str, Any]:
        return {
            "policy": self.policy.to_json(),
            "calls": self.calls,
            "retries": self.retries,
            "budget_exhausted": self.budget_exhausted,
        }


def _map_workers[T, R](
    items: Iterable[T], operation: Callable[[T], R], *, workers: int
) -> Iterator[tuple[T, R]]:
    """Keep at most ``workers`` futures queued; programming faults stop new work."""
    pending_items = iter(items)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {}

        def submit():
            try:
                item = next(pending_items)
            except StopIteration:
                return
            pending[pool.submit(operation, item)] = item

        for _ in range(workers):
            submit()
        try:
            while pending:
                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    item = pending.pop(future)
                    yield item, future.result()
                    submit()
        finally:
            for future in pending:
                future.cancel()
