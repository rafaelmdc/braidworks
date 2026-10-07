"""Serializable operational options validate before touching the filesystem."""

import pytest
from braidworks.core import CachePolicy, QueryPersistence


def test_json_roundtrip_and_memory_defaults(tmp_path):
    options = QueryPersistence(
        str(tmp_path / "cache.sqlite"),
        str(tmp_path / "runs.sqlite"),
        "example",
        CachePolicy(60, 5, 1024),
        30,
    )
    assert QueryPersistence.from_json(options.to_json()) == options
    assert not list(tmp_path.iterdir())
    assert QueryPersistence().cache() is None
    with pytest.raises(ValueError, match="path"):
        QueryPersistence().store()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"run_id": "orphan"},
        {"run_db": ""},
        {"cache_db": False},
        {"lease_seconds": 0},
        {"lease_seconds": float("inf")},
        {"lease_seconds": True},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        QueryPersistence(**kwargs)


def test_future_configuration_version_rejects():
    with pytest.raises(ValueError, match="version"):
        QueryPersistence.from_json({"version": 999})
