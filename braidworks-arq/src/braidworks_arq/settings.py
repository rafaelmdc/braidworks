"""Redis connection + per-weaver queue naming, all environment-driven.

- ``BRAIDWORKS_REDIS_URL`` — the Redis arq uses for both the queue and job results
  (default ``redis://localhost:6379/0``).

Per-weaver queues (``queue_for``) are how data locality and global rate-limiting are
expressed: a worker that holds the NCBI database serves the ``ncbi`` queue, and an
upstream-throttled weaver gets its own queue with a sized worker pool.
"""

from __future__ import annotations

import os

from arq.connections import RedisSettings

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
QUEUE_PREFIX = "weaver."


def redis_url() -> str:
    return os.environ.get("BRAIDWORKS_REDIS_URL", DEFAULT_REDIS_URL)


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(redis_url())


def queue_for(weaver_id: str) -> str:
    """The dedicated queue name a weaver's steps are routed to."""
    return f"{QUEUE_PREFIX}{weaver_id}"
