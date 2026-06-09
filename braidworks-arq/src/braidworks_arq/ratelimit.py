"""Global (cluster-wide) token-bucket rate limiting against shared upstreams.

A fleet of N workers must share one budget to stay under an API's published limit, so
the bucket lives in Redis (a small atomic Lua script: refill-then-take). It is async
to fit arq's event-loop worker — ``acquire`` awaits, sleeping with ``asyncio.sleep``
rather than blocking the loop, and reuses the worker's own async Redis connection.

Opt-in and off by default: set ``BRAIDWORKS_RATE_LIMITS`` to a comma list of
``weaver[:backend]=rate_per_sec`` (e.g. ``ncbi:api=3,uniprot=10``). A step matching a
rule must acquire a token before it runs (see ``tasks.weave_step``); unmatched steps
are never throttled.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Protocol

# Refill by elapsed*rate (capped at capacity), then take one token if available.
# Returns "-1" on success, else the seconds to wait before retrying (as a string).
_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local state = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(state[1])
local ts = tonumber(state[2])
if tokens == nil then tokens = capacity; ts = now end
local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * rate)
local ttl = math.ceil(capacity / rate) + 1
if tokens >= 1 then
  tokens = tokens - 1
  redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
  redis.call('EXPIRE', key, ttl)
  return "-1"
else
  redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
  redis.call('EXPIRE', key, ttl)
  return tostring((1 - tokens) / rate)
end
"""


class AsyncRedisLike(Protocol):
    """The slice of an async redis client this module uses."""

    async def eval(self, script: str, numkeys: int, *keys_and_args): ...  # noqa: A003


def _as_float(raw: object) -> float:
    return float(raw.decode() if isinstance(raw, bytes) else raw)


@dataclass
class TokenBucket:
    """A cluster-wide async token bucket. ``rate`` tokens/sec, burst up to ``capacity``."""

    redis: AsyncRedisLike
    key: str
    rate: float
    capacity: float

    async def acquire(self, *, timeout: float | None = None) -> bool:
        """Take one token, awaiting until one is free. False if ``timeout`` elapses."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            wait = await self._try_take()
            if wait < 0:
                return True
            if deadline is not None and time.monotonic() + wait > deadline:
                return False
            await asyncio.sleep(min(wait, 0.5))

    async def _try_take(self) -> float:
        raw = await self.redis.eval(_LUA, 1, self.key, self.rate, self.capacity, time.time())
        return _as_float(raw)


def parse_rate_limits(spec: str | None) -> dict[str, float]:
    """Parse ``BRAIDWORKS_RATE_LIMITS`` into ``{"weaver[:backend]": rate}``.

    Empty/unset → no limits. Malformed entries are skipped (a typo must never make a
    worker silently refuse all work).
    """
    limits: dict[str, float] = {}
    if not spec:
        return limits
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        target, _, rate = chunk.partition("=")
        try:
            limits[target.strip()] = float(rate)
        except ValueError:
            continue
    return limits


def rate_for(limits: dict[str, float], weaver_id: str, backend: str) -> float | None:
    """Most-specific match: ``weaver:backend`` beats bare ``weaver``."""
    return limits.get(f"{weaver_id}:{backend}", limits.get(weaver_id))


def load_limits() -> dict[str, float]:
    return parse_rate_limits(os.environ.get("BRAIDWORKS_RATE_LIMITS"))
