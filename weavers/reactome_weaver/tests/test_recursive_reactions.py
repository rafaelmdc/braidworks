"""Recursive event reference identities and full fan sets remain source-backed."""

import httpx
import pytest
from reactome_weaver.backends.api import ReactomeApiBackend, _contained, _InvalidResponse


def test_jackson_reference_reused_without_guessing():
    reaction = {"dbId": 2, "stId": "R-HSA-2", "schemaClass": "Reaction"}
    pathway = {"dbId": 1, "stId": "R-HSA-1", "schemaClass": "Pathway", "hasEvent": [reaction]}
    rows = _contained([pathway, 2])
    assert [r["stId"] for r in rows] == ["R-HSA-1", "R-HSA-2"]
    with pytest.raises(_InvalidResponse, match="Unresolved"):
        _contained([999])


async def test_recursive_listing_caps_display_not_fan_and_deduplicates_inputs():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json=[
                {"dbId": n, "stId": f"R-HSA-{n}", "schemaClass": "Reaction", "isInferred": n == 1}
                for n in range(1, 23)
            ],
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://test"
    ) as client:
        backend = ReactomeApiBackend(client=client, limit=2)
        rows = await backend.fetch(
            "list_reactions",
            [{"pathway.reactome.id": "R-HSA-10"}] * 2,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert len(calls) == 1
    assert len(rows[0].values["reaction.reactome.id"]) == 22
    value = rows[0].values["pathway.reactome.reactions"]
    assert value["count"] == 22 and len(value["records"]) == 2
    value["records"].clear()
    assert len(rows[1].values["pathway.reactome.reactions"]["records"]) == 2


async def test_reaction_description_batches_many_into_one_request_and_retains_evidence():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "POST"
        return httpx.Response(
            200,
            json=[
                {
                    "stId": identifier,
                    "schemaClass": "Reaction",
                    "isInferred": True,
                    "inferredFrom": [{"stId": "R-MMU-1"}],
                    "literatureReference": [{"pubMedIdentifier": 1}],
                }
                for identifier in request.content.decode().split(",")
            ],
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://test"
    ) as client:
        backend = ReactomeApiBackend(client=client)
        rows = await backend.fetch(
            "describe_reaction",
            [{"reaction.reactome.id": "R-HSA-1"}, {"reaction.reactome.id": "R-HSA-2"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"detail"}),
        )
    assert len(calls) == 1
    assert all(r.values["reaction.reactome.detail"]["is_inferred"] for r in rows)
    assert rows[0].values["reaction.reactome.detail"]["literature"] == [{"pubMedIdentifier": 1}]
