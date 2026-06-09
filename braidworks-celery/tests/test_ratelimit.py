"""Token-bucket parsing/matching + bucket behavior against a tiny fake Redis."""

from __future__ import annotations

from braidworks_celery.ratelimit import (
    TokenBucket,
    parse_rate_limits,
    rate_for,
)


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


class FakeRedis:
    """A minimal eval-only Redis emulating the token-bucket Lua well enough to test.

    It does not run Lua; it reimplements the same refill-then-take math over an
    in-process dict so the bucket's blocking/refill logic can be exercised offline.
    """

    def __init__(self) -> None:
        self.store: dict[str, tuple[float, float]] = {}

    def eval(self, script, numkeys, *args):  # noqa: A003
        key = args[0]
        rate, capacity, now = float(args[1]), float(args[2]), float(args[3])
        tokens, ts = self.store.get(key, (capacity, now))
        tokens = min(capacity, tokens + max(0.0, now - ts) * rate)
        if tokens >= 1:
            self.store[key] = (tokens - 1, now)
            return "-1"
        self.store[key] = (tokens, now)
        return str((1 - tokens) / rate)


def test_bucket_allows_burst_then_blocks():
    fake = FakeRedis()
    bucket = TokenBucket(fake, key="k", rate=1.0, capacity=2.0)
    # capacity 2 → two immediate takes succeed without waiting.
    assert bucket._try_take() < 0
    assert bucket._try_take() < 0
    # third take is empty → returns a positive wait (~1s at 1/s).
    wait = bucket._try_take()
    assert wait > 0


def test_acquire_times_out_when_starved():
    fake = FakeRedis()
    bucket = TokenBucket(fake, key="k", rate=0.001, capacity=1.0)
    assert bucket.acquire(timeout=None) is True  # first token is free
    assert bucket.acquire(timeout=0.05) is False  # refill far too slow within timeout
