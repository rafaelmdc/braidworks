"""End-to-end tree placement: crosswalk → leaf accession → root path → patristic.

This exercises the whole per-entity-then-pairwise flow a consumer (e.g. ORDINA's
phylogeny layer) runs: fetch each organism's ``gtdb.tree.rootpath`` independently, then
reduce pairs of paths to distances with :func:`gtdb_weaver.cophenetic`.
"""

from __future__ import annotations

import pytest
from gtdb_weaver import cophenetic
from gtdb_weaver.backends.local import GtdbLocalBackend
from gtdb_weaver.fixture import fixture_db_path, fixture_tree_path

# taxid -> the fixture-tree leaf it should place onto (its species rep accession).
_ECOLI, _OPACIMONAS, _RUMINO, _AVISPIR, _JABGUH = "562", "1905676", "41978", "3048838", "2053517"


def _backend() -> GtdbLocalBackend:
    return GtdbLocalBackend(fixture_db_path(), tree_paths=[fixture_tree_path()])


async def _rootpaths(taxids: list[str]) -> dict[str, list]:
    records = await _backend().fetch(
        "describe_gtdb_tree_placement",
        [{"ncbi.taxon.id": t} for t in taxids],
        requested_outputs=frozenset({"gtdb.tree.rootpath"}),
        groups_to_compute=frozenset({"core"}),
    )
    return {
        t: r.values["gtdb.tree.rootpath"] for t, r in zip(taxids, records) if r.found and r.values
    }


async def test_places_all_fixture_taxa():
    paths = await _rootpaths([_ECOLI, _OPACIMONAS, _RUMINO, _AVISPIR, _JABGUH])
    assert set(paths) == {_ECOLI, _OPACIMONAS, _RUMINO, _AVISPIR, _JABGUH}


async def test_resolves_by_name_too():
    records = await _backend().fetch(
        "describe_gtdb_tree_placement",
        [{"organism.scientific_name": "Escherichia coli"}],
        requested_outputs=frozenset({"gtdb.tree.rootpath"}),
        groups_to_compute=frozenset({"core"}),
    )
    assert records[0].found


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (_ECOLI, _OPACIMONAS, 0.75),  # siblings under Pseudomonadota: 0.25 + 0.5
        (_RUMINO, _AVISPIR, 0.625),  # siblings under Bacillota: 0.25 + 0.375
        (_ECOLI, _RUMINO, 1.5),  # across phyla, via the root: 0.75 + 0.75
        (_ECOLI, _ECOLI, 0.0),  # an organism to itself
    ],
)
async def test_patristic_distance_between_placed_taxa(a, b, expected):
    paths = await _rootpaths([a, b])
    assert cophenetic(paths[a], paths[b]) == pytest.approx(expected)


async def test_unknown_taxon_is_a_miss_not_an_error():
    records = await _backend().fetch(
        "describe_gtdb_tree_placement",
        [{"ncbi.taxon.id": "999999999"}],
        requested_outputs=frozenset({"gtdb.tree.rootpath"}),
        groups_to_compute=frozenset({"core"}),
    )
    assert records[0].found is False


async def test_without_a_tree_placement_misses_but_taxonomy_still_works():
    """A backend with the crosswalk but no tree file: placement misses, lineage works."""
    treeless = GtdbLocalBackend(fixture_db_path())  # no tree_paths
    placement = await treeless.fetch(
        "describe_gtdb_tree_placement",
        [{"ncbi.taxon.id": _ECOLI}],
        requested_outputs=frozenset({"gtdb.tree.rootpath"}),
        groups_to_compute=frozenset({"core"}),
    )
    assert placement[0].found is False
    taxonomy = await treeless.fetch(
        "describe_gtdb_taxonomy",
        [{"ncbi.taxon.id": _ECOLI}],
        requested_outputs=frozenset({"gtdb.taxon.id"}),
        groups_to_compute=frozenset({"core"}),
    )
    assert taxonomy[0].found and taxonomy[0].values["gtdb.taxon.id"] == "s__Escherichia coli"


async def test_whole_batch_runs_off_event_loop(monkeypatch):
    import asyncio
    import threading

    backend = _backend()
    started, release = threading.Event(), threading.Event()

    def slow_batch(capability, queries):
        started.set()
        assert release.wait(5)
        return []

    monkeypatch.setattr(backend, "_fetch_sync", slow_batch)
    task = asyncio.create_task(
        backend.fetch(
            "describe_gtdb_taxonomy",
            [],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    )
    try:

        async def heartbeat():
            while not started.is_set():
                await asyncio.sleep(0)
            assert not task.done()

        await asyncio.wait_for(heartbeat(), timeout=2)
    finally:
        release.set()
        await task


async def test_tree_change_requires_reopen(tmp_path):
    from braidworks.core.exceptions import BackendConfigurationError

    path = tmp_path / "tree"
    path.write_text(fixture_tree_path().read_text())
    backend = GtdbLocalBackend(fixture_db_path(), tree_paths=[path])
    first = backend.fingerprint()
    path.write_text("(replacement:1);")
    with pytest.raises(BackendConfigurationError, match="reopen"):
        await backend.fetch(
            "describe_gtdb_tree_placement",
            [{"ncbi.taxon.id": _ECOLI}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert GtdbLocalBackend(fixture_db_path(), tree_paths=[path]).fingerprint() != first
