"""UniProt search and asynchronous mapping-job response boundaries."""

import asyncio

import httpx
import pytest
from uniprot_weaver import mapping
from uniprot_weaver.backends.api import UniprotApiBackend


async def fetch(handler, capability="resolve_protein", queries=None, outputs=frozenset()):
    queries = (
        queries if queries is not None else [{"protein.query": "Bad"}, {"protein.query": "Good"}]
    )
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        return await UniprotApiBackend(client=client).fetch(
            capability, queries, requested_outputs=outputs, groups_to_compute=frozenset()
        )


@pytest.mark.parametrize(
    "body",
    [
        b"broken",
        b"null",
        b"{}",
        b'{"results":[null]}',
        b'{"results":[{"primaryAccession":"P1","proteinDescription":{"recommendedName":{"fullName":[]}}}]}',
        b'{"results":[{"primaryAccession":"P1","genes":[null]}]}',
        b'{"results":[{"primaryAccession":"P1","comments":[{"commentType":"FUNCTION","texts":[null]}]}]}',
    ],
)
async def test_invalid_search_does_not_abort_siblings(body):
    def handler(request):
        return (
            httpx.Response(200, json={"results": [{"primaryAccession": "P1"}]})
            if "Good" in request.url.params["query"]
            else httpx.Response(200, content=body)
        )

    records = await fetch(handler)
    assert records[0].error and not records[0].found
    assert records[1].found and not records[1].error


@pytest.mark.parametrize("status", [400, 404, 500])
async def test_search_status_convention(status):
    records = await fetch(lambda r: httpx.Response(status), queries=[{"protein.query": "Bad"}])
    assert not records[0].found and bool(records[0].error) == (status == 500)


@pytest.mark.parametrize(
    "phase,body",
    [
        ("run", b"{}"),
        ("run", b"null"),
        ("status", b"{}"),
        ("status", b"null"),
        ("results", b"null"),
        ("results", b"{}"),
        ("results", b'{"results":[null]}'),
        ("results", b'{"results":[{"from":"OTHER","to":"P1"}]}'),
        ("results", b'{"results":[{"from":"1","to":[]}]}'),
    ],
)
async def test_bad_job_data_is_error(phase, body):
    def handler(request):
        if request.url.path.endswith("/run"):
            return (
                httpx.Response(200, content=body)
                if phase == "run"
                else httpx.Response(200, json={"jobId": "job"})
            )
        if "/status/" in request.url.path:
            return (
                httpx.Response(200, content=body)
                if phase == "status"
                else httpx.Response(200, json={"jobStatus": "FINISHED"})
            )
        return httpx.Response(200, content=body)

    records = await fetch(handler, mapping.TO_ACCESSION, [{"gene.ncbi.id": "1"}, {}])
    assert records[0].error and not records[0].found
    assert not records[1].error and not records[1].found


async def test_one_source_mapping_job_failure_keeps_other_source(monkeypatch):
    from uniprot_weaver.backends import api

    monkeypatch.setattr(api, "_IDMAP_POLL_DELAY", 0)

    def handler(request):
        if request.url.path.endswith("/run"):
            if b"GeneID" in request.content:
                return httpx.Response(404)
            return httpx.Response(200, json={"jobId": "good"})
        if "/status/" in request.url.path:
            return httpx.Response(200, json={"jobStatus": "FINISHED"})
        return httpx.Response(200, json={"results": [{"from": "ENS1", "to": "P1"}]})

    queries = [{"gene.ncbi.id": "1"}, {"gene.ensembl.id": "ENS1"}, {}]
    records = await fetch(handler, mapping.TO_ACCESSION, queries)
    assert records[0].error and records[1].found and not records[1].error
    assert not records[2].found and not records[2].error


@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError, ValueError])
async def test_control_and_programming_faults_propagate(failure):
    async def handler(request):
        raise failure()

    with pytest.raises(failure):
        await fetch(handler, queries=[{"protein.query": "Bad"}])
