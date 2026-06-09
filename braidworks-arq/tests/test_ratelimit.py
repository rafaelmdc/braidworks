"""Token-bucket parsing/matching + async bucket behavior against a fake async Redis."""

from __future__ import annotations

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

    async def eval(self, script, numkeys, *args):  # noqa: A003
        key = args[0]
        rate, capacity, now = float(args[1]), float(args[2]), float(args[3])
        cost = min(float(args[4]) if len(args) > 4 else 1.0, capacity)
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
