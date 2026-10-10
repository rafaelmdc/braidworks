"""Evidence polarity, filters and ontology relations retain their distinct meanings."""

import httpx
from quickgo_weaver.backends.api import QuickgoApiBackend, _aggregate, _relations


def test_not_rows_do_not_create_positive_term_membership():
    rows = [
        {"goId": "GO:1", "goName": "negative only", "qualifier": "NOT|enables"},
        {"goId": "GO:2", "goName": "mixed", "qualifier": "NOT|enables"},
        {"goId": "GO:2", "goName": "mixed", "qualifier": "enables"},
    ]
    values = _aggregate(rows)
    assert values["go.term"] == ["GO:2"] and values["go.count"] == 1
    record = QuickgoApiBackend._annotation_record({}, rows, {"complete": True})
    assert len(record.values["go.annotation.records"]) == 3
    assert record.values["go.annotation.coverage"]["negative_annotations"] == 2


def test_relations_are_typed_children_without_inferred_parents_or_replacements():
    source = {
        "id": "GO:1",
        "isObsolete": True,
        "children": [
            {"id": "GO:2", "relation": "is_a"},
            {"id": "GO:2", "relation": "part_of"},
            {"id": "GO:2", "relation": "is_a"},
        ],
    }
    detail = _relations(source)
    assert len(detail["children"]) == 2 and detail["is_obsolete"]
    assert detail["parents"] is None and detail["replacement_ids"] is None
    assert _relations({"id": "GO:1"})["children"] is None


async def test_exact_filters_reach_bulk_request_and_are_recorded():
    calls = []

    def handler(request):
        calls.append(request)
        ids = request.url.params["geneProductId"].split(",")
        rows = [
            {
                "goId": "GO:0006915",
                "goName": "apoptosis",
                "goAspect": "biological_process",
                "geneProductId": "UniProtKB:" + accession,
                "qualifier": "involved_in",
                "evidenceCode": "ECO:0000315",
            }
            for accession in ids
        ]
        return httpx.Response(
            200,
            json={
                "results": rows,
                "numberOfHits": len(rows),
                "pageInfo": {"current": 1, "total": 1},
            },
        )

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        backend = QuickgoApiBackend(client=client)
        queries = [{"protein.uniprot.accession": a} for a in ["P04637", "P69905", "P04637"]]
        records = await backend.fetch(
            "list_go_terms",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
            params={
                "evidence_code": "ECO:0000315",
                "evidence_usage": "exact",
                "aspect": "biological_process",
                "qualifier": "involved_in",
            },
        )
        assert len(calls) == 1 and len(records) == 3
        assert calls[0].url.params["evidenceCodeUsage"] == "exact"
        assert calls[0].url.params["qualifier"] == "involved_in"
        assert (
            records[0].values["go.annotation.coverage"]["filters"]["evidenceCode"] == "ECO:0000315"
        )
        records[0].values["go.annotation.records"][0]["goId"] = "mutated"
        assert records[2].values["go.annotation.records"][0]["goId"] == "GO:0006915"
        invalid = await backend.fetch(
            "list_go_terms",
            queries[:1],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
            params={"evidence_code": "IMP"},
        )
        assert invalid[0].error and len(calls) == 1
