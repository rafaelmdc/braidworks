"""Opt-in integration tests that need a real Redis (the Lua bucket can't run inline).

Enable by pointing ``BRAIDWORKS_REDIS_TEST`` at a Redis URL, e.g.::

    BRAIDWORKS_REDIS_TEST=redis://localhost:6379/15 \
        uv run --extra test python -m pytest tests/test_integration_redis.py

Skips entirely when unset, so the default suite stays broker-free.
"""

from __future__ import annotations

import os

import pytest

_URL = os.environ.get("BRAIDWORKS_REDIS_TEST")
pytestmark = pytest.mark.skipif(not _URL, reason="set BRAIDWORKS_REDIS_TEST to run")


@pytest.fixture()
async def client():
    redis = pytest.importorskip("redis.asyncio", reason="redis.asyncio required")
    c = redis.from_url(_URL)
    await c.flushdb()
    yield c
    await c.flushdb()
    await c.aclose()


async def test_token_bucket_lua_enforces_rate(client):
    from braidworks_arq.ratelimit import TokenBucket

    bucket = TokenBucket(client, key="braidworks:test:rl", rate=5.0, capacity=5.0)
    for _ in range(5):
        assert await bucket._try_take() < 0
    assert await bucket._try_take() > 0
    assert await bucket.acquire(timeout=0.05) is False


async def test_weighted_take_against_real_lua(client):
    from braidworks_arq.ratelimit import TokenBucket

    bucket = TokenBucket(client, key="braidworks:test:rl:w", rate=1.0, capacity=5.0)
    assert await bucket._try_take(5) < 0  # drains the burst in one weighted take
    assert await bucket._try_take(1) > 0  # empty now
