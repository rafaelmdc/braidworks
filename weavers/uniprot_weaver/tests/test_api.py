"""Unit tests for the UniProt api backend — the novel search + mapping logic.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They
exercise: field extraction, taxid coercion to int (the bridge key), FUNCTION
evidence-stripping, the reviewed→unreviewed fallback, sparse unreviewed entries,
misses, blank queries, and per-entity error handling.
"""

from __future__ import annotations

import json

import httpx

from uniprot_weaver.backends.api import UniprotApiBackend, _pick

CAP = "resolve_protein"
ALL_OUTPUTS = frozenset(
    {
        "protein.uniprot.accession",
        "protein.name",
        "protein.gene",
        "protein.organism",
        "protein.reviewed",
        "ncbi.taxon.id",
        "protein.function",
        "protein.length",
    }
)

_TP53 = {
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "primaryAccession": "P04637",
    "organism": {"scientificName": "Homo sapiens", "taxonId": 9606},
    "proteinDescription": {"recommendedName": {"fullName": {"value": "Cellular tumor antigen p53"}}},
    "genes": [{"geneName": {"value": "TP53"}}],
    "comments": [
        {
            "commentType": "FUNCTION",
            "texts": [{"value": "Acts as a tumor suppressor (PubMed:11025664) in many tumors."}],
        }
    ],
    "sequence": {"length": 393},
}


def _backend(*, reviewed=None, unreviewed=None, status=200, calls=None):
    """A backend whose search returns ``reviewed`` for reviewed:true queries, else ``unreviewed``."""

    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status, content=b"{}")
        if not request.url.path.endswith("/uniprotkb/search"):
            return httpx.Response(404, content=b"{}")
        is_reviewed = "reviewed:true" in request.url.params.get("query", "")
        hit = reviewed if is_reviewed else unreviewed
        return httpx.Response(200, content=json.dumps({"results": [hit] if hit else []}))

    client = httpx.AsyncClient(base_url="https://u", transport=httpx.MockTransport(handler))
    return UniprotApiBackend(client=client)


async def _one(backend, term):
    records = await backend.fetch(
        CAP, [{"protein.query": term}], requested_outputs=ALL_OUTPUTS, groups_to_compute=frozenset()
    )
    assert len(records) == 1
    return records[0]


async def test_extracts_all_fields():
    record = await _one(_backend(reviewed=_TP53), "TP53")
    v = record.values
    assert record.found is True
    assert v["protein.uniprot.accession"] == "P04637"
    assert v["protein.gene"] == "TP53"
    assert v["protein.name"] == "Cellular tumor antigen p53"
    assert v["protein.organism"] == "Homo sapiens"
    assert v["protein.reviewed"] == "reviewed"
    assert v["protein.length"] == 393


async def test_taxid_is_the_bridge_key_as_int():
    v = (await _one(_backend(reviewed=_TP53), "TP53")).values
    assert v["ncbi.taxon.id"] == 9606 and isinstance(v["ncbi.taxon.id"], int)


async def test_function_evidence_is_stripped():
    fn = (await _one(_backend(reviewed=_TP53), "TP53")).values["protein.function"]
    assert "PubMed" not in fn and fn == "Acts as a tumor suppressor in many tumors."


async def test_falls_back_to_unreviewed_when_no_reviewed_hit():
    unreviewed = {
        "entryType": "UniProtKB unreviewed (TrEMBL)",
        "primaryAccession": "A0A0X1",
        "organism": {"scientificName": "Escherichia coli", "taxonId": 562},
    }
    record = await _one(_backend(reviewed=None, unreviewed=unreviewed), "someprotein")
    assert record.found is True
    assert record.values["protein.reviewed"] == "unreviewed"
    assert record.values["protein.uniprot.accession"] == "A0A0X1"


async def test_sparse_unreviewed_entry_does_not_crash():
    # TrEMBL entries often lack recommendedName / genes / function / sequence.
    sparse = {"entryType": "UniProtKB unreviewed (TrEMBL)", "primaryAccession": "X1",
              "organism": {"scientificName": "Bacillus subtilis", "taxonId": 1423}}
    v = (await _one(_backend(reviewed=None, unreviewed=sparse), "x")).values
    assert v["protein.uniprot.accession"] == "X1"
    assert "protein.gene" not in v and "protein.function" not in v


async def test_no_results_is_a_miss():
    record = await _one(_backend(reviewed=None, unreviewed=None), "nonsense")
    assert record.found is False and record.error is None


async def test_blank_query_makes_no_call():
    calls: list[str] = []
    record = await _one(_backend(calls=calls), "   ")
    assert record.found is False and record.error is None and calls == []


async def test_http_error_becomes_per_entity_error():
    record = await _one(_backend(status=500), "TP53")
    assert record.found is False and record.error is not None and "UniProt" in record.error


def test_pick_is_deterministic_best_score_then_accession():
    # Same candidate set, any input order -> same pick: max annotation score, then
    # accession ascending. (Determinism is the contract; relevance ranking is not stable.)
    page = [
        {"primaryAccession": "P99999", "annotationScore": 5.0},
        {"primaryAccession": "O09185", "annotationScore": 5.0},
        {"primaryAccession": "P04637", "annotationScore": 5.0},
        {"primaryAccession": "A0HIGH", "annotationScore": 3.0},
    ]
    assert _pick(page)["primaryAccession"] == "O09185"  # score-5 tie -> lowest accession
    assert _pick(list(reversed(page)))["primaryAccession"] == "O09185"  # order-independent
    assert _pick([{"primaryAccession": "Z9", "annotationScore": 2.0}])["primaryAccession"] == "Z9"


def test_fingerprint_is_stable_and_real():
    fp = UniprotApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp
