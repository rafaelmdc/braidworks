"""Different upstream mapping targets must never satisfy each other's cache lookup."""

import pytest
from braidworks.core import Strand, StrandSet
from braidworks.core.cache import InMemoryStrandCache
from braidworks.core.executor import LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from braidworks.core.sqlite_cache import SQLiteStrandCache
from tests.test_api import ACC, COUNT, RECORDS, _idmap_backend
from uniprot_weaver.mapping import TO_DB
from uniprot_weaver.weaver import UniprotWeaver


@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("targets", [("gene.ncbi.id", "pdb.id"), ("pdb.id", "gene.ncbi.id")])
async def test_target_requests_do_not_reuse_other_target_cache(tmp_path, persistent, targets):
    calls = []
    backend = _idmap_backend(
        {
            ("UniProtKB_AC-ID", "GeneID"): {"P04637": ["7157"]},
            ("UniProtKB_AC-ID", "PDB"): {"P04637": ["1TUP"]},
        },
        run_calls=calls,
    )
    registry = BraidRegistry()
    registry.register(UniprotWeaver({"api": backend}))
    cache = SQLiteStrandCache(tmp_path / "cache") if persistent else InMemoryStrandCache()
    executor = LocalExecutor(registry, cache=cache)
    for target in targets:
        braid = Braider(registry).plan(frozenset({ACC}), frozenset({target}))
        result = await executor.execute(
            braid, [StrandSet.from_strands("p53", [Strand(ACC, "P04637")])]
        )
        assert result.resolved[0].get(target).value == (
            7157 if target == "gene.ncbi.id" else "1TUP"
        )
    assert calls == [("UniProtKB_AC-ID", TO_DB[target]) for target in targets]
    await backend._client.aclose()


@pytest.mark.parametrize("output", [COUNT, RECORDS])
async def test_summary_only_fetches_all_supported_targets(output):
    calls = []
    backend = _idmap_backend(
        {
            ("UniProtKB_AC-ID", "GeneID"): {"P04637": ["7157"]},
            ("UniProtKB_AC-ID", "PDB"): {"P04637": ["1TUP"]},
        },
        run_calls=calls,
    )
    record = (
        await backend.fetch(
            "map_from_accession",
            [{ACC: "P04637"}],
            requested_outputs=frozenset({output}),
            groups_to_compute=frozenset({"summary"}),
        )
    )[0]
    assert record.found and record.values[COUNT] == 2
    assert {row["db"] for row in record.values[RECORDS]} == {"GeneID", "PDB"}
    assert calls == [("UniProtKB_AC-ID", db) for db in TO_DB.values()]
    await backend._client.aclose()
