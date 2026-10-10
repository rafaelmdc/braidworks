"""Typed ontology paths and bounded reverse correlation."""

import httpx
from quickgo_weaver.backends.api import QuickgoApiBackend


async def test_reverse_batches_many_into_one_request_and_keeps_negative_evidence():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["goId"] == "GO:0000001,GO:0000002"
        assert request.url.params["goUsage"] == "exact"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "goId": "GO:0000001",
                        "geneProductId": "UniProtKB:P1",
                        "qualifier": "involved_in",
                    },
                    {"goId": "GO:0000002", "geneProductId": "UniProtKB:P2", "qualifier": "NOT"},
                ],
                "numberOfHits": 2,
                "pageInfo": {"current": 1, "total": 1},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://test"
    ) as client:
        backend = QuickgoApiBackend(client=client)
        records = await backend.fetch(
            "list_gene_products",
            [{"go.term": "GO:0000001"}, {"go.term": "GO:0000002"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert len(calls) == 1
    assert records[0].values["protein.uniprot.accession"] == ["P1"]
    assert records[1].values["protein.uniprot.accession"] == []
    assert records[1].values["go.reverse.annotations"][0]["qualifier"] == "NOT"


async def test_hierarchy_retains_replacement_direction_and_typed_parents():
    def handler(request):
        path = request.url.path
        row = {"id": "GO:0006915", "name": "apoptotic process", "isObsolete": False}
        if path.endswith("/complete"):
            row["replaces"] = [{"id": "GO:0006918", "type": "consider"}]
        if path.endswith("/ancestors"):
            row["ancestors"] = ["GO:0006915", "GO:0008150"]
        if "/paths/" in path:
            return httpx.Response(
                200,
                json={
                    "results": [
                        [{"child": "GO:0006915", "parent": "GO:0008150", "relationship": "is_a"}]
                    ]
                },
            )
        return httpx.Response(200, json={"results": [row]})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://test"
    ) as client:
        backend = QuickgoApiBackend(client=client)
        result = (
            await backend.fetch(
                "describe_go_term",
                [{"go.term": "GO:0006915"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset({"hierarchy"}),
            )
        )[0]
    hierarchy = result.values["go.term.hierarchy"]
    assert hierarchy["parents"] == [{"id": "GO:0008150", "relation": "is_a"}]
    assert hierarchy["replacements"] is None
    assert hierarchy["replaces"][0]["type"] == "consider"
