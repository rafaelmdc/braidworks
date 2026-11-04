"""Single-ID HTTP work is bounded, duplicate-safe, paced and cancellation-safe."""

import asyncio

import httpx
import pytest
from braidworks.core.http_pacing import request_budget
from ncbi_weaver import vocab
from ncbi_weaver.backends.datasets_v2 import DatasetsV2Backend, _enrich
from ncbi_weaver.intermediate import TaxonMatch, TaxonMatchStatus


@pytest.mark.parametrize(
    "operation,key",
    [
        ("list_children", vocab.TAXON_ID),
        ("list_genomes", vocab.TAXON_ID),
        ("list_orthologs", vocab.GENE_ID),
    ],
)
async def test_single_id_batches_share_duplicates_bound_requests_and_preserve_queries(
    operation, key
):
    active = peak = 0
    calls, charges = [], []

    async def handler(request):
        nonlocal active, peak
        calls.append(request.url.path)
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            return httpx.Response(200, json={"reports": []})
        finally:
            active -= 1

    async def charge(*target):
        charges.append(target)

    queries = [{key: k, "position": i} for i, k in enumerate(["1", "2", "1", "3"])]
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        backend = DatasetsV2Backend(client=client, max_concurrency=2)
        with request_budget(charge):
            method = getattr(backend, operation)
            records = await (
                method(queries, rank="species") if operation == "list_children" else method(queries)
            )
    assert len(calls) == len(charges) == 3
    assert peak == 2 and active == 0
    assert [r.query for r in records] == queries
    assert all(not r.found and not r.error for r in records)
    assert records[0] is not records[2]


async def test_fuzzy_fallbacks_keep_exact_bulk_and_bound_distinct_names(monkeypatch):
    backend = DatasetsV2Backend(max_concurrency=2)
    active = peak = 0
    exact_calls, fuzzy_calls = [], []

    async def exact(names):
        exact_calls.append(names)
        return {}

    async def fuzzy(name):
        nonlocal active, peak
        fuzzy_calls.append(name)
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            return TaxonMatch(query=name, status=TaxonMatchStatus.NO_MATCH)
        finally:
            active -= 1

    monkeypatch.setattr(backend, "_dataset_report", exact)
    monkeypatch.setattr(backend, "_fuzzy_match", fuzzy)
    names = ["a", "b", "a", "c"]
    records = await backend.resolve(vocab.RESOLVE_NAME, names, need_lineage=False)
    assert len(exact_calls) == 1 and len(fuzzy_calls) == 3
    assert peak == 2 and [r.query for r in records] == names


async def test_optional_enrichment_is_bounded_and_deduplicated():
    active = peak = 0
    calls = []

    async def fetch(identifier):
        nonlocal active, peak
        calls.append(identifier)
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            if identifier == "bad":
                raise httpx.ConnectError("unavailable")
            return [{"id": identifier}]
        finally:
            active -= 1

    values, errors = await _enrich(fetch, ["a", "bad", "a", "b"], limit=2)
    assert peak == 2 and len(calls) == 3 and active == 0
    assert set(values) == {"a", "b"} and set(errors) == {"bad"}


async def test_cancelled_batch_joins_workers_and_starts_no_remaining_requests():
    started = asyncio.Event()
    active = 0
    calls = []

    async def handler(request):
        nonlocal active
        calls.append(request)
        active += 1
        if active == 2:
            started.set()
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1

    async def charge(*_):
        pass

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        backend = DatasetsV2Backend(client=client, max_concurrency=2)
        with request_budget(charge):
            task = asyncio.create_task(
                backend.list_genomes([{vocab.TAXON_ID: i} for i in range(1, 10)])
            )
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert active == 0 and len(calls) == 2


@pytest.mark.parametrize("limit", [True, 0, -1, 1.5])
def test_invalid_concurrency_is_rejected(limit):
    with pytest.raises(ValueError, match="max_concurrency"):
        DatasetsV2Backend(max_concurrency=limit)
