"""Requested event detail preserves entity types and source identifier scope."""

import httpx
from reactome_weaver.backends.api import ReactomeApiBackend, _hierarchy, _participants


def test_direct_hierarchy_and_mixed_participant_types():
    obj = {
        "stId": "R-HSA-1",
        "schemaClass": "Pathway",
        "hasEvent": [
            {"stId": "R-HSA-2", "schemaClass": "Reaction"},
            {"stId": "R-HSA-3", "schemaClass": "Pathway"},
        ],
    }
    result = _hierarchy(obj)
    assert [r["type"] for r in result["children"]] == ["Reaction", "Pathway"]
    assert _hierarchy({"stId": "R-HSA-4", "schemaClass": "Reaction"})["children"] is None
    rows = [
        {"peDbId": 2, "schemaClass": "Complex", "refEntities": []},
        {
            "peDbId": 1,
            "schemaClass": "SimpleEntity",
            "refEntities": [{"identifier": "15377", "schemaClass": "ReferenceMolecule"}],
        },
    ]
    output = _participants(rows, "R-HSA-1", 97)
    assert [r["type"] for r in output["records"]] == ["SimpleEntity", "Complex"]
    assert all(r["observed_release"] == 97 for r in output["records"])
    assert output["records"][1]["references"] == []


async def test_defaults_skip_expansion_and_requested_participants_reuse_duplicate():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/database/version"):
            assert request.headers["Accept"] == "text/plain"
            return httpx.Response(200, text="97")
        if "/participants/" in request.url.path:
            return httpx.Response(
                200, json=[{"peDbId": 1, "schemaClass": "Complex", "refEntities": []}]
            )
        ids = request.content.decode().split(",")
        return httpx.Response(
            200,
            json=[
                {
                    "stId": pid,
                    "displayName": "fixture",
                    "schemaClass": "Pathway",
                    "hasEvent": [{"stId": "R-HSA-3", "schemaClass": "Reaction"}],
                }
                for pid in ids
            ],
        )

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        backend = ReactomeApiBackend(client=client)
        queries = [{"pathway.reactome.id": p} for p in ["R-HSA-1", "R-HSA-2", "R-HSA-1"]]
        await backend.fetch(
            "describe_pathway",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"detail"}),
        )
        assert len(calls) == 1
        records = await backend.fetch(
            "describe_pathway",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"hierarchy", "participants"}),
        )
        assert (
            len(calls) == 5
        )  # one bulk summary, one release request, two single-ID participant requests
        assert all(r.found for r in records)
        assert records[0].values["pathway.reactome.hierarchy"]["children"][0]["id"] == "R-HSA-3"
        records[0].values["pathway.reactome.participants"]["records"][0]["type"] = "mutated"
        assert records[2].values["pathway.reactome.participants"]["records"][0]["type"] == "Complex"
