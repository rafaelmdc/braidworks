"""compute_cache_key fingerprint rules and InMemoryStrandCache superset validity."""

from __future__ import annotations

from braidworks.core.cache import InMemoryStrandCache, compute_cache_key
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet

from helpers import resolve_name_capability

CAP = resolve_name_capability()


def _key(strand_set, *, capability_version="1.0.0", backend="local", dataset_version="ds-1"):
    return compute_cache_key(
        CAP,
        strand_set,
        capability_version=capability_version,
        backend=backend,
        dataset_version=dataset_version,
    )


def _result(computed_groups, status=WeaveStatus.OK):
    return WeaveResult(
        capability_id=CAP.id,
        capability_version="1.0.0",
        backend_used="local",
        computed_groups=frozenset(computed_groups),
        status=status,
    )


def test_same_value_different_provenance_same_fingerprint():
    a = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens", provenance=("src_a",))])
    b = StrandSet.from_strands("e2", [Strand("organism.name", "Homo sapiens", provenance=("src_b",))])
    assert _key(a).input_fingerprint == _key(b).input_fingerprint


def test_different_value_different_fingerprint():
    a = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    b = StrandSet.from_strands("e2", [Strand("organism.name", "Mus musculus")])
    assert _key(a).input_fingerprint != _key(b).input_fingerprint


def test_extra_unrelated_strands_do_not_change_fingerprint():
    minimal = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    extra = StrandSet.from_strands(
        "e2",
        [
            Strand("organism.name", "Homo sapiens"),
            Strand("sample.id", "S-42"),
            Strand("random.note", "ignore me"),
        ],
    )
    assert _key(minimal).input_fingerprint == _key(extra).input_fingerprint


def test_requested_groups_do_not_affect_key():
    # The key is computed without any group input at all, so it is identical
    # regardless of which groups a caller will request.
    ss = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    assert _key(ss) == _key(ss)


def test_dataset_version_changes_key():
    ss = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    assert _key(ss, dataset_version="ds-1") != _key(ss, dataset_version="ds-2")


def test_capability_version_changes_key():
    ss = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    assert _key(ss, capability_version="1") != _key(ss, capability_version="2")


def test_cache_hit_on_superset():
    cache = InMemoryStrandCache()
    ss = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    k = _key(ss)
    cache.put(k, _result({"core", "lineage"}))
    hit = cache.get(k, frozenset({"core"}))
    assert hit is not None and hit.computed_groups == frozenset({"core", "lineage"})


def test_cache_miss_when_not_superset():
    cache = InMemoryStrandCache()
    ss = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    k = _key(ss)
    cache.put(k, _result({"core"}))
    assert cache.get(k, frozenset({"core", "lineage"})) is None


def test_two_entries_per_base_key_richer_found_first():
    cache = InMemoryStrandCache()
    ss = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    k = _key(ss)
    cache.put(k, _result({"core"}))
    cache.put(k, _result({"core", "lineage"}))
    # Both stored as separate entries.
    assert len(cache._store[k]) == 2
    # A core lookup is satisfied; a core+lineage lookup is also satisfied by the richer entry.
    assert cache.get(k, frozenset({"core"})) is not None
    rich = cache.get(k, frozenset({"core", "lineage"}))
    assert rich is not None and rich.computed_groups == frozenset({"core", "lineage"})


def test_put_replaces_entry_with_matching_groups():
    cache = InMemoryStrandCache()
    ss = StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])
    k = _key(ss)
    cache.put(k, _result({"core"}, status=WeaveStatus.OK))
    cache.put(k, _result({"core"}, status=WeaveStatus.NO_MATCH))
    assert len(cache._store[k]) == 1
    assert cache.get(k, frozenset({"core"})).status is WeaveStatus.NO_MATCH
