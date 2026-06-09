"""Opt-in integration tests that need a real Redis (the Lua bucket can't run eager).

Enable by pointing ``BRAIDWORKS_REDIS_TEST`` at a Redis URL, e.g.::

    BRAIDWORKS_REDIS_TEST=redis://localhost:6379/15 \
        uv run --extra test python -m pytest tests/test_integration_redis.py

The whole module skips when that env var is unset, so the default suite stays
broker-free.
"""

from __future__ import annotations

import os
import time

import pytest

_URL = os.environ.get("BRAIDWORKS_REDIS_TEST")
pytestmark = pytest.mark.skipif(not _URL, reason="set BRAIDWORKS_REDIS_TEST to run")


@pytest.fixture()
def client():
    redis = pytest.importorskip("redis")
    c = redis.Redis.from_url(_URL)
    c.flushdb()
    yield c
    c.flushdb()


def test_token_bucket_lua_enforces_rate_across_calls(client):
    from braidworks_celery.ratelimit import TokenBucket

    bucket = TokenBucket(client, key="braidworks:test:rl", rate=5.0, capacity=5.0)
    # Drain the burst capacity.
    for _ in range(5):
        assert bucket._try_take() < 0
    # Now empty: a take reports a positive wait, and acquire honors a short timeout.
    assert bucket._try_take() > 0
    assert bucket.acquire(timeout=0.05) is False


def test_token_bucket_refills_over_time(client):
    from braidworks_celery.ratelimit import TokenBucket

    bucket = TokenBucket(client, key="braidworks:test:rl2", rate=20.0, capacity=1.0)
    assert bucket._try_take() < 0  # take the only token
    assert bucket._try_take() > 0  # empty
    time.sleep(0.1)  # 20/s → ~2 tokens refilled
    assert bucket._try_take() < 0
