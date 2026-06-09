"""Global token-bucket rate limiting against shared upstreams (e.g. NCBI).

Celery's built-in ``rate_limit`` is *per worker*; a fleet of 10 workers each
allowed "3/s" hits an upstream at 30/s. This is a **cluster-wide** limiter backed by
Redis, so N workers share one budget — the thing you actually need to stay under an
API's published limit.

Configuration is environment-driven and opt-in (off by default). Set
``BRAIDWORKS_RATE_LIMITS`` to a comma list of ``weaver_id[:backend]=rate_per_sec``,
e.g. ``ncbi:api=3,uniprot=10``. A step matching a rule must acquire a token before
it runs (see ``tasks.weave_step``); steps with no rule are never throttled.

The bucket is a small atomic Lua script (refill-then-take) so concurrent workers
can't race past the budget. ``acquire`` blocks (sleeping) until a token is free.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol

# Refill the bucket by elapsed*rate (capped at capacity), then take one token if
# available. Returns 1 on success, else the seconds to wait before retrying.
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
if tokens >= 1 then
  tokens = tokens - 1
  redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
  redis.call('EXPIRE', key, math.ceil(capacity / rate) + 1)
  return "-1"
else
  redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
  redis.call('EXPIRE', key, math.ceil(capacity / rate) + 1)
  return tostring((1 - tokens) / rate)
end
"""


class RedisLike(Protocol):
    """The slice of the redis client this module uses (eval-based)."""

    def eval(self, script: str, numkeys: int, *keys_and_args): ...  # noqa: A003


@dataclass
class TokenBucket:
    """A cluster-wide token bucket. ``rate`` tokens/sec, burst up to ``capacity``."""

    redis: RedisLike
    key: str
    rate: float
    capacity: float

    def acquire(self, *, timeout: float | None = None) -> bool:
        """Take one token, sleeping until one is free. False if ``timeout`` elapses."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            wait = self._try_take()
            if wait < 0:
                return True
            if deadline is not None and time.monotonic() + wait > deadline:
                return False
            time.sleep(min(wait, 0.5))

    def _try_take(self) -> float:
        raw = self.redis.eval(_LUA, 1, self.key, self.rate, self.capacity, time.time())
        return float(raw)


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


def rate_for(
    limits: dict[str, float], weaver_id: str, backend: str
) -> float | None:
    """Most-specific match: ``weaver:backend`` beats bare ``weaver``."""
    return limits.get(f"{weaver_id}:{backend}", limits.get(weaver_id))


def load_limits() -> dict[str, float]:
    return parse_rate_limits(os.environ.get("BRAIDWORKS_RATE_LIMITS"))
