"""STRING decoding, correlation and chunk-scoped failure values."""

import asyncio

import httpx
import pytest
from string_weaver.backends import api
from string_weaver.backends.api import StringApiBackend


@pytest.mark.parametrize("phase", ["mapping", "partners"])
@pytest.mark.parametrize(
    "body", [b"broken", b"null", b"{}", b"[null]", b'[{"queryItem":"OTHER","stringId":"id"}]']
)
async def test_bad_source_is_error(phase, body):
    def handler(request):
        if phase == "partners" and request.url.path.endswith("get_string_ids"):
            return httpx.Response(200, json=[{"queryItem": "P1", "stringId": "9606.ID1"}])
        return httpx.Response(200, content=body)

    queries = [{"protein.uniprot.accession": "P1"}, {"protein.uniprot.accession": ""}]
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        records = await StringApiBackend(client=client).fetch(
            "list_interactions",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert records[0].error and not records[0].found
    assert not records[1].error and not records[1].found


@pytest.mark.parametrize("phase", ["mapping", "partners"])
async def test_failed_chunk_keeps_other_chunks(monkeypatch, phase):
    monkeypatch.setattr(api, "_ID_CHUNK", 1)
    calls = []

    def handler(request):
        ids = request.url.params["identifiers"]
        calls.append(ids)
        mapping = request.url.path.endswith("get_string_ids")
        if (phase == "mapping" and mapping and ids == "P2") or (
            phase == "partners" and not mapping and ids == "9606.IDP2"
        ):
            return httpx.Response(503)
        return httpx.Response(
            200,
            json=[{"queryItem": ids, "stringId": "9606.ID" + ids}]
            if mapping
            else [
                {
                    "stringId_A": ids,
                    "stringId_B": "9606.partner",
                    "preferredName_B": "partner",
                    "score": 0.9,
                }
            ],
        )

    queries = [{"protein.uniprot.accession": acc} for acc in ("P3", "P2", "P1", "P2", "")]
    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        records = await StringApiBackend(client=client).fetch(
            "list_interactions",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert [r.query for r in records] == queries
    assert [r.found for r in records] == [True, False, True, False, False]
    assert records[1].error and records[1].error == records[3].error
    assert "P3" in calls and "9606.IDP3" in calls


@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError, ValueError])
async def test_control_and_programming_faults_propagate(failure):
    async def handler(request):
        raise failure()

    async with httpx.AsyncClient(
        base_url="https://source", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(failure):
            await StringApiBackend(client=client).fetch(
                "list_interactions",
                [{"protein.uniprot.accession": "P1"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )


async def test_competing_string_identities_for_one_accession_are_an_error():
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=[
                    {"queryItem": "P1", "stringId": identifier}
                    for identifier in ["9606.P1", "10090.P1"]
                ],
            ),
        ),
    ) as client:
        records = await StringApiBackend(client=client).fetch(
            "list_interactions",
            [{"protein.uniprot.accession": "P1"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert records[0].error and not records[0].found
    assert "10090.P1" in records[0].error and "9606.P1" in records[0].error
