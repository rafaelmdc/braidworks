"""Validate both QuickGO response seams without turning source errors into misses."""

import asyncio

import httpx
import pytest
from quickgo_weaver.backends import api
from quickgo_weaver.backends.api import QuickgoApiBackend


@pytest.mark.parametrize(
    "cap,key", [("list_go_terms", "protein.uniprot.accession"), ("describe_go_term", "go.term")]
)
@pytest.mark.parametrize(
    "body", [b"broken", b"null", b"{}", b'{"results":[null]}', b'{"results":{}}']
)
async def test_malformed_source_is_error(cap, key, body):
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)),
    ) as client:
        queries = [{key: "P1"}, {key: ""}]
        records = await QuickgoApiBackend(client=client).fetch(
            cap, queries, requested_outputs=frozenset(), groups_to_compute=frozenset()
        )
    assert [r.query for r in records] == queries
    assert records[0].error and not records[0].found
    assert not records[1].error and not records[1].found


@pytest.mark.parametrize(
    "extra",
    [
        {"pageInfo": []},
        {"pageInfo": {"total": -1}},
        {"pageInfo": {"total": "2"}},
        {"pageInfo": {"current": 2}},
        {"numberOfHits": True},
        {"numberOfHits": -1},
    ],
)
async def test_invalid_page_metadata_is_error(extra):
    payload = {"results": [{"goId": "GO:1", "geneProductId": "UniProtKB:P1"}], **extra}
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
    ) as client:
        records = await QuickgoApiBackend(client=client).fetch(
            "list_go_terms",
            [{"protein.uniprot.accession": "P1"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert records[0].error


async def test_singleton_wrong_echo_is_error():
    payload = {
        "results": [{"goId": "GO:1", "geneProductId": "UniProtKB:OTHER"}],
        "pageInfo": {"total": 1},
    }
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
    ) as client:
        records = await QuickgoApiBackend(client=client).fetch(
            "list_go_terms",
            [{"protein.uniprot.accession": "P1"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert records[0].error


async def test_detail_chunk_failure_preserves_siblings(monkeypatch):
    monkeypatch.setattr(api, "_TERM_CHUNK", 1)
    calls = []

    def handler(request):
        key = request.url.path.rsplit("/", 1)[-1]
        calls.append(key)
        if key == "GO:2":
            return httpx.Response(200, json={"results": [None]})
        return httpx.Response(200, json={"results": [{"id": key, "name": "term"}]})

    queries = [{"go.term": key} for key in ["GO:3", "GO:2", "GO:1", "GO:2"]]
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        records = await QuickgoApiBackend(client=client).fetch(
            "describe_go_term",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert calls == ["GO:1", "GO:2", "GO:3"]
    assert [r.found for r in records] == [True, False, True, False]
    assert records[1].error == records[3].error and records[1].error


async def test_cancellation_propagates():
    async def handler(request):
        raise asyncio.CancelledError()

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(asyncio.CancelledError):
            await QuickgoApiBackend(client=client).fetch(
                "list_go_terms",
                [{"protein.uniprot.accession": "P1"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )


async def test_live_empty_zero_page_convention_is_no_match():
    payload = {
        "numberOfHits": 0,
        "results": [],
        "pageInfo": {"resultsPerPage": 200, "current": 0, "total": 0},
    }
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
    ) as client:
        records = await QuickgoApiBackend(client=client).fetch(
            "list_go_terms",
            [{"protein.uniprot.accession": "UNKNOWN"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert not records[0].found and not records[0].error


@pytest.mark.parametrize("echo", [None, "", "UniProtKB:OTHER"])
@pytest.mark.parametrize("accessions", [["P1"], ["P1", "P2", "P1"]])
async def test_annotation_identity_required_for_singleton_and_batch(echo, accessions):
    row = {"goId": "GO:1"}
    if echo is not None:
        row["geneProductId"] = echo
    payload = {"results": [row], "pageInfo": {"total": 1}}
    queries = [{"protein.uniprot.accession": accession} for accession in accessions]
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    ) as client:
        records = await QuickgoApiBackend(client=client).fetch(
            "list_go_terms",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert [record.query for record in records] == queries
    assert all(record.error and not record.found for record in records)
