"""Adverse source data and direct multi-chunk failure isolation."""

import asyncio

import httpx
import pytest
from pdbe_weaver.backends import api
from pdbe_weaver.backends.api import PdbeApiBackend


async def fetch(client, capability, queries):
    return await PdbeApiBackend(client=client).fetch(
        capability, queries, requested_outputs=frozenset(), groups_to_compute=frozenset()
    )


@pytest.mark.parametrize(
    "capability,key",
    [("list_structures", "protein.uniprot.accession"), ("describe_structure", "pdb.id")],
)
@pytest.mark.parametrize("body", [b"not-json", b"null", b"42", b"[null]", b'{"unexpected":{}}'])
async def test_malformed_source_is_error(capability, key, body):
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)),
    ) as client:
        queries = [{key: "P1" if capability == "list_structures" else "D1"}, {key: ""}]
        records = await fetch(client, capability, queries)
    assert [r.query for r in records] == queries
    assert records[0].error and not records[0].found
    assert not records[1].error and not records[1].found


@pytest.mark.parametrize("failure", [500, 404, "json", "shape"])
async def test_details_preserve_good_chunks_and_attempt_later_work(monkeypatch, failure):
    monkeypatch.setattr(api, "_SUMMARY_CHUNK", 1)
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
        body = {pid: [{"title": pid, "experimental_method": ["X-ray diffraction"]}]}
        return httpx.Response(200, json=body)

    queries = [{"pdb.id": pid} for pid in ("D3", "D2", "D1", "D2", "")]
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handle)
    ) as client:
        records = await fetch(client, "describe_structure", queries)
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
            await fetch(client, "describe_structure", [{"pdb.id": "D1"}])


async def test_programming_errors_propagate():
    def handle(request):
        raise RuntimeError("bug")

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(RuntimeError, match="bug"):
            await fetch(client, "describe_structure", [{"pdb.id": "D1"}])
