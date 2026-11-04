"""Cluster-wide token-bucket input dispatch throttling.

A fleet shares one input dispatch budget in Redis (an atomic Lua refill-then-take
script). It is async to fit arq's event-loop worker — ``acquire`` awaits, sleeping with ``asyncio.sleep``
rather than blocking the loop, and reuses the worker's own async Redis connection.

Opt-in and off by default: set ``BRAIDWORKS_RATE_LIMITS`` to a comma list of
``weaver[:backend]=inputs_per_sec`` (e.g. ``ncbi:api=3,uniprot=10``). A step matching a
rule must acquire a token before it runs (see ``tasks.weave_step``); unmatched steps
are never throttled.
"""

from __future__ import annotations

import asyncio
import math
import os
import time
from dataclasses import dataclass
from typing import Protocol

from braidworks.core.http_pacing import parse_rate_limits, rate_for

__all__ = ["TokenBucket", "load_limits", "parse_rate_limits", "rate_for"]

# Refill by elapsed*rate (capped at capacity), then take ``cost`` tokens if available.
# Returns "-1" on success, else the seconds to wait before the cost can be met (string).
# Each take is at most capacity; acquire splits larger costs without discarding tokens.
_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local cost = tonumber(ARGV[4])
local state = redis.call('HMGET', key, 'tokens', 'ts', 'rate', 'capacity')
if state[3] and (tonumber(state[3]) ~= rate or tonumber(state[4]) ~= capacity) then
  return 'config_mismatch'
end
local tokens = tonumber(state[1])
local ts = tonumber(state[2])
if tokens == nil then tokens = capacity; ts = now end
local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * rate)
local ttl = math.ceil(capacity / rate) + 1
if tokens >= cost then
  tokens = tokens - cost
  redis.call('HMSET', key, 'tokens', tokens, 'ts', now, 'rate', rate, 'capacity', capacity)
  redis.call('EXPIRE', key, ttl)
  return "-1"
else
  redis.call('HMSET', key, 'tokens', tokens, 'ts', now, 'rate', rate, 'capacity', capacity)
  redis.call('EXPIRE', key, ttl)
  return tostring((cost - tokens) / rate)
end
"""


class AsyncRedisLike(Protocol):
    """The slice of an async redis client this module uses."""

    async def eval(self, script: str, numkeys: int, *keys_and_args): ...


def _as_float(raw: object) -> float:
    return float(raw.decode() if isinstance(raw, bytes) else raw)


@dataclass
class TokenBucket:
    """A cluster-wide async token bucket. ``rate`` tokens/sec, burst up to ``capacity``."""

    redis: AsyncRedisLike
    key: str
    rate: float
    capacity: float

    def __post_init__(self) -> None:
        for name, value in (("rate", self.rate), ("capacity", self.capacity)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

    async def acquire(self, cost: float = 1.0, *, timeout: float | None = None) -> bool:
        """Charge the full cost, waiting for refill as needed.

        Oversized costs are split into capacity-sized takes. A timeout or cancellation
        does not refund earlier takes. This budgets input dispatch; it does not count
        or pace HTTP requests inside the backend.
        """
        if not math.isfinite(cost) or cost <= 0:
            raise ValueError("cost must be finite and positive")
        if timeout is not None and (not math.isfinite(timeout) or timeout < 0):
            raise ValueError("timeout must be finite and nonnegative")
        deadline = None if timeout is None else time.monotonic() + timeout
        remaining = cost
        while remaining > 0:
            portion = min(remaining, self.capacity)
            while True:
                wait = await self._try_take(portion)
                if wait < 0:
                    break
                if deadline is not None and time.monotonic() + wait > deadline:
                    return False
                await asyncio.sleep(min(wait, 0.5))
            remaining -= portion
        return True

    async def _try_take(self, cost: float = 1.0) -> float:
        if not math.isfinite(cost) or not 0 < cost <= self.capacity:
            raise ValueError("one take must have finite cost in (0, capacity]")
        raw = await self.redis.eval(_LUA, 1, self.key, self.rate, self.capacity, time.time(), cost)
        if raw in {"config_mismatch", b"config_mismatch"}:
            from braidworks.core.exceptions import BackendConfigurationError

            raise BackendConfigurationError(
                "workers disagree on Redis request rate or burst capacity"
            )
        return _as_float(raw)


def load_limits() -> dict[str, float]:
    return parse_rate_limits(os.environ.get("BRAIDWORKS_RATE_LIMITS"))
