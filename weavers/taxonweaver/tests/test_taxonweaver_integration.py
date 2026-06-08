"""End-to-end stack (registry -> braider -> executor -> weaver -> cache) plus
dispatch and factory behavior."""

from __future__ import annotations

import httpx
import pytest

from braidworks.core import (
    BackendConfigurationError,
    BackendUnavailable,
    Braider,
    BraidRegistry,
    InMemoryStrandCache,
    LocalExecutor,
    Strand,
    StrandSet,
)

from taxonweaver import build_ncbi_weaver, vocab

RESOLVABLE = [
    "Faecalibacterium prausnitzii",
    "Faecalibacterium altus",
    "Faecalibacterium minor",
    "Faecalibacterium",
    "Bacteria",
]


def _name_sets(names):
    return [
        StrandSet.from_strands(f"e{i}", [Strand(vocab.ORGANISM_NAME, n)])
        for i, n in enumerate(names)
    ]


async def test_end_to_end_resolves_with_lineage_and_caches(mini_db_path):
    registry = BraidRegistry()
    weaver = build_ncbi_weaver(db_path=mini_db_path)
    registry.register(weaver)

    # Count actual backend work to prove the cache short-circuits the second run.
    backend = weaver._backends["local"]
    original_resolve = backend.resolve
    calls: list[int] = []

    async def counting_resolve(*args, **kwargs):
        calls.append(1)
        return await original_resolve(*args, **kwargs)

    backend.resolve = counting_resolve

    braid = Braider(registry).plan(
        frozenset({vocab.ORGANISM_NAME}),
        frozenset({vocab.TAXON_ID, vocab.LINEAGE}),
    )
    assert len(braid.steps) == 1  # coalesced into one invocation

    executor = LocalExecutor(registry, InMemoryStrandCache())
    sets = _name_sets(RESOLVABLE + ["Zzqq nonexistent organism"])

    first = await executor.execute(braid, sets)
    assert len(first.resolved) == len(RESOLVABLE)
    assert len(first.unresolved) == 1
    for ss in first.resolved:
        assert ss.has(vocab.TAXON_ID)
        assert ss.has(vocab.LINEAGE)
    assert sum(calls) >= 1

    calls_after_first = sum(calls)
    second = await executor.execute(braid, _name_sets(RESOLVABLE + ["Zzqq nonexistent organism"]))
    assert len(second.resolved) == len(RESOLVABLE)
    # Second run is fully served from cache: no further backend resolve calls.
    assert sum(calls) == calls_after_first


async def test_unconfigured_backend_raises_backend_unavailable(mini_db_path):
    weaver = build_ncbi_weaver(db_path=mini_db_path)  # local only, no api
    ss = StrandSet.from_strands("e", [Strand(vocab.ORGANISM_NAME, "Bacteria")])
    with pytest.raises(BackendUnavailable):
        await weaver.execute_batch(
            vocab.RESOLVE_NAME, [ss], requested_outputs=frozenset({vocab.TAXON_ID}), backend="api"
        )


def test_factory_requires_at_least_one_backend():
    with pytest.raises(BackendConfigurationError):
        build_ncbi_weaver()


def test_factory_local_only_manifest_declares_local(mini_db_path):
    weaver = build_ncbi_weaver(db_path=mini_db_path)
    for cap in weaver.MANIFEST.capabilities:
        assert cap.backends == ("local",)


def test_factory_both_backends_declared(mini_db_path):
    client = httpx.AsyncClient(base_url="https://api.test/v2", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    weaver = build_ncbi_weaver(db_path=mini_db_path, api_client=client)
    for cap in weaver.MANIFEST.capabilities:
        assert cap.backends == ("api", "local")


def test_unconfigured_backend_fingerprint_is_stable(mini_db_path):
    weaver = build_ncbi_weaver(db_path=mini_db_path)
    assert weaver.backend_fingerprint("api") == "unconfigured:api"
