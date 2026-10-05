import json
from dataclasses import replace

import pytest
from braidworks.core.cache import InMemoryStrandCache, StrandCacheKey
from braidworks.core.cache_codec import canonical_json
from braidworks.core.cache_policy import CachePolicy
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.sqlite import connection_scope, transaction
from braidworks.core.sqlite_cache import SQLiteStrandCache
from braidworks.core.strand import Strand

KEY = StrandCacheKey("source", "1", "source.lookup", "local", "generation", "input")


def result(groups=("core",), status=WeaveStatus.OK):
    return WeaveResult(
        "source.lookup",
        "1",
        "local",
        frozenset(groups),
        status,
        strands=(Strand("output.value", "value"),) if status is WeaveStatus.OK else (),
    )


@pytest.mark.parametrize("persistent", [False, True])
def test_shared_coverage_contract(tmp_path, persistent):
    cache = SQLiteStrandCache(tmp_path / "cache") if persistent else InMemoryStrandCache()
    cache.put(KEY, result(("core", "extra")))
    assert cache.get(KEY, frozenset({"core"})).computed_groups == frozenset({"core", "extra"})
    assert cache.get(KEY, frozenset({"missing"})) is None
    cache.put(KEY, result(("core",), WeaveStatus.NO_MATCH))
    assert cache.get(KEY, frozenset({"core"})) is not None
    assert cache.get(replace(KEY, backend_fingerprint="changed"), frozenset({"core"})) is None
    cache.put(replace(KEY, input_fingerprint="error"), result(status=WeaveStatus.ERROR))
    assert cache.get(replace(KEY, input_fingerprint="error"), frozenset()) is None


@pytest.mark.parametrize(
    "status,ttl",
    [(WeaveStatus.OK, 3600), (WeaveStatus.NO_MATCH, 300), (WeaveStatus.AMBIGUOUS, 3600)],
)
def test_reopen_and_fake_clock_expiry(tmp_path, status, ttl):
    now = [100.0]
    path = tmp_path / "cache"
    first = SQLiteStrandCache(path, clock=lambda: now[0])
    stored = result(status=status)
    stored.requires_review = status is WeaveStatus.AMBIGUOUS
    first.put(KEY, stored)
    first.close()
    second = SQLiteStrandCache(path, clock=lambda: now[0])
    assert second.get(KEY, frozenset({"core"})).to_json() == stored.to_json()
    now[0] += ttl
    assert second.get(KEY, frozenset({"core"})) is None


def test_zero_ttl_and_budget_disable_admission(tmp_path):
    cache = SQLiteStrandCache(tmp_path / "cache", policy=CachePolicy(0, 0))
    for status in WeaveStatus:
        cache.put(KEY, result(status=status))
    assert cache.get(KEY, frozenset()) is None
    cache = SQLiteStrandCache(tmp_path / "disabled", policy=CachePolicy(max_payload_bytes=0))
    cache.put(KEY, result())
    assert cache.get(KEY, frozenset()) is None


def test_deterministic_superset_selection(tmp_path):
    cache = SQLiteStrandCache(tmp_path / "cache")
    for groups in (("core", "z"), ("core", "a"), ("core", "z", "a")):
        cache.put(KEY, result(groups))
    assert cache.get(KEY, frozenset({"core"})).computed_groups == frozenset({"core", "a"})


def test_corruption_is_reported_as_miss(tmp_path, caplog):
    path = tmp_path / "cache"
    cache = SQLiteStrandCache(path)
    cache.put(KEY, result())
    with connection_scope(path) as connection, transaction(connection):
        connection.execute("UPDATE strand_cache_entries SET payload='not-json'")
    assert cache.get(KEY, frozenset()) is None
    assert "corrupt cache entry" in caplog.text


def test_future_schema_is_rejected_even_by_existing_adapter(tmp_path):
    path = tmp_path / "cache"
    cache = SQLiteStrandCache(path)
    with connection_scope(path) as connection, transaction(connection):
        connection.execute("UPDATE strand_cache_meta SET codec_version=999")
    with pytest.raises(ValueError, match="schema/codec"):
        SQLiteStrandCache(path)
    with pytest.raises(ValueError, match="schema/codec"):
        cache.get(KEY, frozenset())


def test_payload_budget_evicts_oldest_and_oversize(tmp_path):
    size = len(canonical_json(result().to_json()).encode())
    cache = SQLiteStrandCache(
        tmp_path / "cache", policy=CachePolicy(max_payload_bytes=size), clock=lambda: 1
    )
    cache.put(KEY, result())
    second = replace(KEY, input_fingerprint="second")
    cache.put(second, result())
    assert cache.get(KEY, frozenset()) is None
    assert cache.get(second, frozenset()) is not None
    cache.put(second, replace(result(), warnings=("larger than budget",)))
    assert cache.get(second, frozenset()) is None


def test_write_failure_preserves_previous_entry(tmp_path):
    path = tmp_path / "cache"
    cache = SQLiteStrandCache(path)
    cache.put(KEY, result())
    with connection_scope(path) as connection, transaction(connection):
        connection.execute(
            "CREATE TRIGGER reject BEFORE INSERT ON strand_cache_entries "
            "BEGIN SELECT RAISE(ABORT, 'stop'); END"
        )
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        cache.put(KEY, result(status=WeaveStatus.NO_MATCH))
    assert cache.get(KEY, frozenset()).status is WeaveStatus.OK


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object(), {1: "bad"}, ("tuple",)])
def test_codec_rejects_unsupported_values(value):
    with pytest.raises((ValueError, TypeError)):
        canonical_json(value)


def test_canonical_order_and_policy_roundtrip():
    assert canonical_json({"b": 2, "a": [1]}) == canonical_json({"a": [1], "b": 2})
    assert CachePolicy.from_json(json.loads(json.dumps(CachePolicy().to_json()))) == CachePolicy()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"positive_ttl": float("nan")},
        {"negative_ttl": -1},
        {"positive_ttl": float("inf")},
        {"max_payload_bytes": -1},
        {"positive_ttl": True},
        {"max_payload_bytes": 1.5},
    ],
)
def test_invalid_policy(kwargs):
    with pytest.raises(ValueError):
        CachePolicy(**kwargs)
