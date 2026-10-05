"""Token-bucket parsing/matching + async bucket behavior against a fake async Redis."""

from __future__ import annotations

import pytest
from braidworks_arq.ratelimit import TokenBucket, parse_rate_limits, rate_for


def test_parse_rate_limits_handles_specificity_and_garbage():
    limits = parse_rate_limits("ncbi:api=3, uniprot=10 , bogus, bad=x")
    assert limits == {"ncbi:api": 3.0, "uniprot": 10.0}
    assert parse_rate_limits(None) == {}
    assert parse_rate_limits("") == {}


def test_rate_for_prefers_weaver_backend_over_bare_weaver():
    limits = {"ncbi": 5.0, "ncbi:api": 2.0}
    assert rate_for(limits, "ncbi", "api") == 2.0
    assert rate_for(limits, "ncbi", "local") == 5.0
    assert rate_for(limits, "other", "api") is None


class FakeAsyncRedis:
    """Reimplements the bucket's refill-then-take math over a dict (no Lua/Redis)."""

    def __init__(self) -> None:
        self.store: dict[str, tuple[float, float]] = {}

    async def eval(self, script, numkeys, *args):
        key = args[0]
        rate, capacity, now = float(args[1]), float(args[2]), float(args[3])
        cost = float(args[4]) if len(args) > 4 else 1.0
        tokens, ts = self.store.get(key, (capacity, now))
        tokens = min(capacity, tokens + max(0.0, now - ts) * rate)
        if tokens >= cost:
            self.store[key] = (tokens - cost, now)
            return "-1"
        self.store[key] = (tokens, now)
        return str((cost - tokens) / rate)


async def test_bucket_allows_burst_then_blocks():
    bucket = TokenBucket(FakeAsyncRedis(), key="k", rate=1.0, capacity=2.0)
    assert await bucket._try_take() < 0
    assert await bucket._try_take() < 0
    assert await bucket._try_take() > 0  # empty → positive wait


async def test_acquire_times_out_when_starved():
    bucket = TokenBucket(FakeAsyncRedis(), key="k", rate=0.001, capacity=1.0)
    assert await bucket.acquire(timeout=None) is True  # first token free
    assert await bucket.acquire(timeout=0.05) is False  # refill too slow


def test_bucket_decodes_bytes_replies():
    from braidworks_arq.ratelimit import _as_float

    assert _as_float(b"-1") == -1.0
    assert _as_float("2.5") == 2.5


async def test_weighted_acquire_consumes_cost_tokens():
    # capacity 5: a single cost-5 take drains the burst, the next must wait.
    bucket = TokenBucket(FakeAsyncRedis(), key="k", rate=1.0, capacity=5.0)
    assert await bucket._try_take(5) < 0
    assert await bucket._try_take(1) > 0  # empty now


async def test_weighted_acquire_partial_budget_blocks():
    bucket = TokenBucket(FakeAsyncRedis(), key="k", rate=1.0, capacity=5.0)
    assert await bucket._try_take(3) < 0  # 5 -> 2 left
    assert await bucket._try_take(3) > 0  # only 2 left, cost 3 → wait


def test_retry_defer_is_jittered_and_bounded():
    from braidworks_arq.tasks import _retry_defer

    # job_try=1 → base 1, full jitter in [0.5, 1.5); always positive, monotone-ish base.
    vals = [_retry_defer(1) for _ in range(50)]
    assert all(0.5 <= v < 1.5 for v in vals)
    assert len(set(vals)) > 1  # actually jittered, not constant
    # job_try=3 → base 4, jitter in [2.0, 6.0)
    assert all(2.0 <= _retry_defer(3) < 6.0 for _ in range(50))


@pytest.mark.parametrize("invalid", [0, -1, float("nan"), float("inf")])
def test_bucket_rejects_invalid_configuration(invalid):
    with pytest.raises(ValueError, match="rate"):
        TokenBucket(FakeAsyncRedis(), key="k", rate=invalid, capacity=1)
    with pytest.raises(ValueError, match="capacity"):
        TokenBucket(FakeAsyncRedis(), key="k", rate=1, capacity=invalid)
    with pytest.raises(ValueError, match="invalid rate limit"):
        parse_rate_limits(f"ncbi={invalid}")


async def test_oversized_acquisition_charges_every_token(monkeypatch):
    from braidworks_arq import ratelimit

    clock = [100.0]
    monkeypatch.setattr(ratelimit.time, "time", lambda: clock[0])
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: clock[0])

    async def advance(seconds):
        clock[0] += seconds

    monkeypatch.setattr(ratelimit.asyncio, "sleep", advance)
    redis = FakeAsyncRedis()
    bucket = TokenBucket(redis, key="k", rate=2, capacity=2)
    assert await bucket.acquire(7)
    # Two tokens initially, five replenished over 2.5 seconds. Nothing is forgiven.
    assert clock[0] == 102.5
    assert redis.store["k"][0] == 0
    assert await bucket._try_take() > 0


async def test_oversized_timeout_does_not_refund_partial_charge():
    redis = FakeAsyncRedis()
    bucket = TokenBucket(redis, key="k", rate=0.001, capacity=2)
    assert await bucket.acquire(3, timeout=0.01) is False
    assert redis.store["k"][0] < 0.01


@pytest.mark.parametrize("invalid", [0, -1, float("nan"), float("inf")])
async def test_acquire_rejects_invalid_cost(invalid):
    bucket = TokenBucket(FakeAsyncRedis(), key="k", rate=1, capacity=1)
    with pytest.raises(ValueError, match="cost"):
        await bucket.acquire(invalid)


async def test_actual_lua_oversized_timeout_and_server_clock():
    from braidworks_arq.ratelimit import _LUA
    from fakeredis import FakeAsyncRedis

    async with FakeAsyncRedis() as redis:
        bucket = TokenBucket(redis, key="actual-lua", rate=0.001, capacity=2)
        assert await bucket.acquire(3, timeout=0.01) is False
        state = await redis.hgetall("actual-lua")
        assert float(state[b"tokens"]) < 0.01
        assert 0 < await redis.ttl("actual-lua") <= 2001
        # An arbitrarily advanced worker clock must not mint tokens.
        reply = await redis.eval(_LUA, 1, "actual-lua", 0.001, 2, 10**15, 1)
        assert float(reply) > 900


async def test_actual_lua_workers_share_one_burst():
    import asyncio

    from fakeredis import FakeAsyncRedis

    async with FakeAsyncRedis() as redis:
        workers = [TokenBucket(redis, key="shared-lua", rate=0.001, capacity=2) for _ in range(3)]
        outcomes = await asyncio.gather(*(worker.acquire(timeout=0) for worker in workers))
        assert outcomes.count(True) == 2
        assert outcomes.count(False) == 1


async def test_actual_lua_rejects_workers_with_different_rate_settings():
    from braidworks.core.exceptions import BackendConfigurationError
    from fakeredis import FakeAsyncRedis

    async with FakeAsyncRedis() as redis:
        first = TokenBucket(redis, key="mixed-config", rate=2, capacity=1)
        assert await first.acquire()
        second = TokenBucket(redis, key="mixed-config", rate=3, capacity=1)
        with pytest.raises(BackendConfigurationError, match="workers disagree"):
            await second.acquire()
