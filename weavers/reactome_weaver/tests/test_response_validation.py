"""Adverse source data and direct multi-chunk failure isolation."""

import asyncio

import httpx
import pytest
from reactome_weaver.backends import api
from reactome_weaver.backends.api import ReactomeApiBackend


async def fetch(client, capability, queries):
    return await ReactomeApiBackend(client=client).fetch(
        capability, queries, requested_outputs=frozenset(), groups_to_compute=frozenset()
    )


@pytest.mark.parametrize(
    "capability,key",
    [("list_pathways", "protein.uniprot.accession"), ("describe_pathway", "pathway.reactome.id")],
)
@pytest.mark.parametrize("body", [b"not-json", b"null", b"42", b"[null]", b'{"unexpected":{}}'])
async def test_malformed_source_is_error(capability, key, body):
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)),
    ) as client:
        queries = [{key: "P1" if capability == "list_pathways" else "D1"}, {key: ""}]
        records = await fetch(client, capability, queries)
    assert [r.query for r in records] == queries
    assert records[0].error and not records[0].found
    assert not records[1].error and not records[1].found


@pytest.mark.parametrize("failure", [500, 404, "json", "shape"])
async def test_details_preserve_good_chunks_and_attempt_later_work(monkeypatch, failure):
    monkeypatch.setattr(api, "_ID_CHUNK", 1)
    calls = []

    def handle(request):
        pid = request.content.decode()
        calls.append(pid)
        if pid == "D2":
            if failure == "json":
                return httpx.Response(200, content=b"not-json")
            if failure == "shape":
                return httpx.Response(200, json=None)
            return httpx.Response(failure)
        body = [{"stId": pid, "displayName": pid}]
        return httpx.Response(200, json=body)

    queries = [{"pathway.reactome.id": pid} for pid in ("D3", "D2", "D1", "D2", "")]
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handle)
    ) as client:
        records = await fetch(client, "describe_pathway", queries)
    assert calls == ["D1", "D2", "D3"]
    assert [r.query for r in records] == queries
    assert [r.found for r in records] == [True, False, True, False, False]
    assert bool(records[1].error) == (failure != 404)
    assert records[1].error == records[3].error
    assert records[-1].error is None


async def test_cancellation_propagates():
    async def handle(request):
        raise asyncio.CancelledError()

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(asyncio.CancelledError):
            await fetch(client, "describe_pathway", [{"pathway.reactome.id": "D1"}])


async def test_programming_errors_propagate():
    def handle(request):
        raise RuntimeError("bug")

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(RuntimeError, match="bug"):
            await fetch(client, "describe_pathway", [{"pathway.reactome.id": "D1"}])
