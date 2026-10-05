"""Unit tests for the QuickGO api backend — dedup, aspect grouping, pagination.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They
exercise: collapsing annotation-evidence rows to distinct GO terms, grouping by
aspect, deterministic GO-id ordering, multi-page fetch, the page cap, and errors.
"""

from __future__ import annotations

import json

import httpx
from quickgo_weaver.backends.api import QuickgoApiBackend

CAP = "list_go_terms"
ALL = frozenset(
    {
        "go.term",
        "go.molecular_function",
        "go.biological_process",
        "go.cellular_component",
        "go.count",
        "go.records",
    }
)


def _ann(go_id, aspect, name=None):
    return {"goId": go_id, "goAspect": aspect, "goName": name or go_id}


def _backend(pages, *, total=None, status=200, calls=None, max_pages=10):
    """A backend serving ``pages`` (1-indexed dict of page -> result rows)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(int(request.url.params.get("page", "1")))
        if status != 200:
            return httpx.Response(status, content=b"{}")
        if request.url.path.endswith("/annotation/search"):
            page = int(request.url.params.get("page", "1"))
            t = total if total is not None else (max(pages) if pages else 1)
            body = {"pageInfo": {"current": page, "total": t}, "results": pages.get(page, [])}
            return httpx.Response(200, content=json.dumps(body))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(
        base_url="https://q/services", transport=httpx.MockTransport(handler)
    )
    return QuickgoApiBackend(client=client, max_pages=max_pages)


async def _one(backend, accession):
    records = await backend.fetch(
        CAP,
        [{"protein.uniprot.accession": accession}],
        requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_dedups_to_distinct_terms_and_groups_by_aspect():
    page = [
        _ann("GO:0006915", "biological_process", "apoptotic process"),
        _ann("GO:0003700", "molecular_function", "DNA-binding TF activity"),
        _ann("GO:0005634", "cellular_component", "nucleus"),
        _ann("GO:0006915", "biological_process", "apoptotic process"),  # duplicate evidence
    ]
    v = (await _one(_backend({1: page}), "P04637")).values
    assert v["go.count"] == 3  # duplicate collapsed
    assert v["go.biological_process"] == ["apoptotic process"]
    assert v["go.molecular_function"] == ["DNA-binding TF activity"]
    assert v["go.cellular_component"] == ["nucleus"]
    # records sorted by GO id (deterministic)
    assert [r["go_id"] for r in v["go.records"]] == ["GO:0003700", "GO:0005634", "GO:0006915"]
    # the fan dimension: every distinct GO id (across aspects), deduped + ordered
    assert v["go.term"] == ["GO:0003700", "GO:0005634", "GO:0006915"]


async def test_paginates_until_total():
    calls: list[int] = []
    pages = {
        1: [_ann("GO:0000001", "biological_process")],
        2: [_ann("GO:0000002", "molecular_function")],
    }
    v = (await _one(_backend(pages, total=2, calls=calls), "P04637")).values
    assert v["go.count"] == 2
    assert calls == [1, 2]  # both pages fetched


async def test_page_cap_bounds_fetch():
    calls: list[int] = []
    pages = {i: [_ann(f"GO:{i:07d}", "biological_process")] for i in range(1, 6)}
    await _one(_backend(pages, total=5, calls=calls, max_pages=2), "P04637")
    assert calls == [1, 2]  # stopped at the cap despite total=5


async def test_empty_is_a_miss():
    record = await _one(_backend({1: []}), "P99999")
    assert record.found is False and record.error is None


async def test_blank_accession_makes_no_call():
    calls: list[int] = []
    record = await _one(_backend({}, calls=calls), "   ")
    assert record.found is False and record.error is None and calls == []


async def test_http_error_becomes_per_entity_error():
    record = await _one(_backend({}, status=500), "P04637")
    assert record.found is False and record.error is not None and "QuickGO" in record.error


def test_fingerprint_is_stable_and_real():
    fp = QuickgoApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp


# --- describe_go_term (one id -> detail) --------------------------------------

_TERM = {
    "id": "GO:0006915",
    "name": "apoptotic process",
    "aspect": "biological_process",
    "definition": {"text": "A programmed cell death process..."},
    "isObsolete": False,
}


def _term_backend(term=None, *, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, content=b"{}")
        if "/ontology/go/terms/" in request.url.path:
            return httpx.Response(200, content=json.dumps({"results": [term] if term else []}))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(
        base_url="https://q/services", transport=httpx.MockTransport(handler)
    )
    return QuickgoApiBackend(client=client)


async def _describe(backend, term_id):
    records = await backend.fetch(
        "describe_go_term",
        [{"go.term": term_id}],
        requested_outputs=frozenset(
            {"go.term.name", "go.term.aspect", "go.term.definition", "go.term.detail"}
        ),
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_describe_go_term_maps_detail():
    rec = await _describe(_term_backend(_TERM), "GO:0006915")
    assert rec.found is True
    v = rec.values
    assert v["go.term.name"] == "apoptotic process"
    assert v["go.term.aspect"] == "biological_process"
    assert v["go.term.definition"].startswith("A programmed cell death")
    assert v["go.term.detail"]["is_obsolete"] is False


async def test_describe_go_term_blank_and_empty_are_misses():
    assert (await _describe(_term_backend(_TERM), "  ")).found is False
    assert (await _describe(_term_backend(None), "GO:9999999")).found is False


async def test_describe_go_term_server_error_is_per_entity_error():
    rec = await _describe(_term_backend(status=500), "GO:0006915")
    assert rec.found is False and rec.error is not None and "QuickGO" in rec.error


async def test_describe_go_term_batches_many_into_one_request():
    """N GO ids -> a single multi-id /ontology/go/terms request, not one per term."""
    terms = {
        "GO:0006915": {
            "id": "GO:0006915",
            "name": "apoptotic process",
            "aspect": "biological_process",
        },
        "GO:0003700": {
            "id": "GO:0003700",
            "name": "DNA-binding TF activity",
            "aspect": "molecular_function",
        },
    }
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        ids = request.url.path.split("/ontology/go/terms/")[1].split(",")
        return httpx.Response(
            200, content=json.dumps({"results": [terms[i] for i in ids if i in terms]})
        )

    client = httpx.AsyncClient(
        base_url="https://q/services", transport=httpx.MockTransport(handler)
    )
    backend = QuickgoApiBackend(client=client)
    records = await backend.fetch(
        "describe_go_term",
        [{"go.term": "GO:0006915"}, {"go.term": "GO:0003700"}, {"go.term": "GO:9999999"}],
        requested_outputs=frozenset({"go.term.name"}),
        groups_to_compute=frozenset(),
    )
    assert [r.found for r in records] == [True, True, False]
    assert records[1].values["go.term.name"] == "DNA-binding TF activity"
    assert len(calls) == 1  # one bulk request for all three ids


async def test_annotation_evidence_and_qualifiers_survive_term_deduplication():
    rows = [
        {
            **_ann("GO:0006915", "biological_process"),
            "id": "b",
            "goEvidence": "ISS",
            "evidenceCode": "ECO:0000250",
            "qualifier": "acts_upstream_of",
        },
        {
            **_ann("GO:0006915", "biological_process"),
            "id": "a",
            "goEvidence": "IDA",
            "evidenceCode": "ECO:0000314",
            "qualifier": "NOT|involved_in",
        },
    ]
    record = await _one(_backend({1: rows}), "P04637")
    assert record.values["go.count"] == 1
    annotations = record.values["go.annotation.records"]
    assert len(annotations) == 2
    assert {r["goEvidence"] for r in annotations} == {"ISS", "IDA"}
    assert {r["qualifier"] for r in annotations} == {"acts_upstream_of", "NOT|involved_in"}
    assert record.values["go.annotation.coverage"]["complete"] is True


async def test_page_cap_is_visible_in_values_and_exported_warnings():
    from braidworks.core import Braider, BraidRegistry, LocalExecutor, Strand, StrandSet
    from braidworks.core.outcomes import execution_records
    from quickgo_weaver.weaver import QuickgoWeaver

    backend = _backend({1: [_ann("GO:0006915", "biological_process")]}, total=3, max_pages=1)
    record = await _one(backend, "P04637")
    coverage = record.values["go.annotation.coverage"]
    assert coverage["complete"] is False
    assert coverage["pages_retrieved"] == 1
    assert coverage["total_pages"] == 3
    assert coverage["reason"] == "page_cap"
    assert record.warnings
    registry = BraidRegistry()
    registry.register(QuickgoWeaver({"api": backend}))
    braid = Braider(registry).plan(
        available_types=frozenset({"protein.uniprot.accession"}),
        target_types=frozenset({"go.count"}),
    )
    executor = LocalExecutor(registry)
    for _ in range(2):  # uncached and cached calls preserve the warning
        result = await executor.execute(
            braid,
            [
                StrandSet.from_strands(
                    "p53",
                    [Strand("protein.uniprot.accession", "P04637")],
                )
            ],
        )
        exported = execution_records(result, ["go.count"])[0]
        assert exported["values"]["go.count"] == 1
        assert any("incomplete" in warning for warning in exported["warnings"])


async def test_missing_page_metadata_does_not_claim_complete():
    def handler(request):
        return httpx.Response(200, json={"results": [_ann("GO:0006915", "biological_process")]})

    backend = QuickgoApiBackend(
        client=httpx.AsyncClient(
            base_url="https://q/services",
            transport=httpx.MockTransport(handler),
        )
    )
    record = await _one(backend, "P04637")
    assert record.values["go.annotation.coverage"]["complete"] is None
    assert record.values["go.annotation.coverage"]["reason"] == "missing_page_info"
    assert record.warnings


async def test_source_count_mismatch_does_not_claim_complete():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "pageInfo": {"total": 1},
                "numberOfHits": 2,
                "results": [_ann("GO:0006915", "biological_process")],
            },
        )

    backend = QuickgoApiBackend(
        client=httpx.AsyncClient(
            base_url="https://q/services",
            transport=httpx.MockTransport(handler),
        )
    )
    record = await _one(backend, "P04637")
    coverage = record.values["go.annotation.coverage"]
    assert coverage["complete"] is False
    assert coverage["reason"] == "row_count_mismatch"
    assert coverage["total_annotations"] == 2
    assert coverage["observed_annotations"] == 1


async def test_annotation_not_found_http_statuses_are_clean_misses():
    for status in (400, 404):
        record = await _one(_backend({}, status=status), "UNKNOWN")
        assert record.found is False
        assert record.error is None


async def test_list_go_terms_batches_many_into_one_request():
    calls = []
    rows = [
        {**_ann("GO:0000001", "biological_process"), "geneProductId": "UniProtKB:P1"},
        {**_ann("GO:0000002", "molecular_function"), "geneProductId": "UniProtKB:P2"},
    ]

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"results": rows, "pageInfo": {"total": 1}, "numberOfHits": 2}
        )

    backend = QuickgoApiBackend(
        client=httpx.AsyncClient(
            base_url="https://q/services",
            transport=httpx.MockTransport(handler),
        )
    )
    queries = [{"protein.uniprot.accession": acc} for acc in ("P2", "P1", "P3", "P1", "")]
    records = await backend.fetch(
        CAP, queries, requested_outputs=ALL, groups_to_compute=frozenset()
    )
    assert len(calls) == 1
    assert calls[0].url.params["geneProductId"] == "P1,P2,P3"
    assert [r.query for r in records] == queries
    assert [r.found for r in records] == [True, True, False, True, False]
    assert records[0].values["go.term"] == ["GO:0000002"]
    assert records[1].values["go.term"] == ["GO:0000001"]
    assert records[0].values["go.annotation.coverage"]["total_annotations"] == 1


async def test_incomplete_bulk_does_not_turn_unseen_accession_into_no_match():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {**_ann("GO:0000001", "biological_process"), "geneProductId": "UniProtKB:P1"}
                ],
                "pageInfo": {"total": 100},
                "numberOfHits": 100,
            },
        )

    backend = QuickgoApiBackend(
        max_pages=1,
        client=httpx.AsyncClient(
            base_url="https://q/services",
            transport=httpx.MockTransport(handler),
        ),
    )
    records = await backend.fetch(
        CAP,
        [{"protein.uniprot.accession": acc} for acc in ("P1", "P2")],
        requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert records[0].found and records[0].warnings
    assert records[1].error and not records[1].found


async def test_bulk_without_echoed_gene_product_ids_is_an_error():
    backend = _backend({1: [_ann("GO:0000001", "biological_process")]})
    records = await backend.fetch(
        CAP,
        [{"protein.uniprot.accession": acc} for acc in ("P1", "P2")],
        requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 2
    assert all(r.error and not r.found for r in records)


async def test_bulk_keeps_per_accession_annotation_cap(monkeypatch):
    from quickgo_weaver.backends import api

    monkeypatch.setattr(api, "_PAGE_SIZE", 1)
    rows = [
        {**_ann("GO:0000001", "biological_process"), "geneProductId": "UniProtKB:P1"},
        {**_ann("GO:0000002", "biological_process"), "geneProductId": "UniProtKB:P1"},
        {**_ann("GO:0000003", "molecular_function"), "geneProductId": "UniProtKB:P2"},
    ]

    def handler(request):
        return httpx.Response(
            200, json={"results": rows, "pageInfo": {"total": 1}, "numberOfHits": 3}
        )

    backend = QuickgoApiBackend(
        max_pages=1,
        client=httpx.AsyncClient(
            base_url="https://q/services",
            transport=httpx.MockTransport(handler),
        ),
    )
    records = await backend.fetch(
        CAP,
        [{"protein.uniprot.accession": acc} for acc in ("P1", "P2")],
        requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    first, second = [r.values["go.annotation.coverage"] for r in records]
    assert first["complete"] is False and first["reason"] == "per_accession_cap"
    assert first["observed_annotations"] == 1 and first["total_annotations"] == 2
    assert second["complete"] is True and second["total_annotations"] == 1
    assert records[0].warnings and not records[1].warnings
