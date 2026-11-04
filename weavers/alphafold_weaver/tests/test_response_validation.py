"""Schema failures must remain local to the affected input."""

import asyncio

import httpx
import pytest
from alphafold_weaver.backends.api import AlphafoldApiBackend


@pytest.mark.parametrize("body", [b"broken", b"null", b"{}", b"[null]", b"42"])
async def test_bad_shape_does_not_abort_siblings(body):
    def handler(request):
        return (
            httpx.Response(200, json=[{"entryId": "AF-GOOD-F1", "globalMetricValue": 90}])
            if "/GOOD/" in request.url.path or request.url.path.endswith("/GOOD")
            else httpx.Response(200, content=body)
        )

    queries = [
        {"protein.uniprot.accession": "BAD"},
        {"protein.uniprot.accession": "GOOD", "extra": "preserved"},
        {"protein.uniprot.accession": None},
        {"protein.uniprot.accession": ""},
    ]
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        records = await AlphafoldApiBackend(client=client).fetch(
            "describe_structure",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert [r.query for r in records] == queries
    assert records[0].error and not records[0].found
    assert records[1].found and not records[1].error
    assert all(not r.found and not r.error for r in records[2:])


async def test_invalid_field_is_error():
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=[{"entryId": "AF-GOOD-F1", "globalMetricValue": "bad"}]
            )
        ),
    ) as client:
        records = await AlphafoldApiBackend(client=client).fetch(
            "describe_structure",
            [{"protein.uniprot.accession": "BAD"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert records[0].error


@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError, ValueError])
async def test_control_and_programming_faults_propagate(failure):
    async def handler(request):
        raise failure()

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(failure):
            await AlphafoldApiBackend(client=client).fetch(
                "describe_structure",
                [{"protein.uniprot.accession": "BAD"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )
