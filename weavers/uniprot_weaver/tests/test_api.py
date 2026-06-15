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


# --- resolve_mapping (gene -> protein bridge) --------------------------------

MAP_CAP = "resolve_mapping"


def _mapping_backend(maps, *, run_calls=None, status="FINISHED", run_status=200, pages=None):
    """A backend serving the ID-mapping flow from ``maps`` = {to_db: {gene_id: [acc, ...]}}.

    Job ids encode the target db (``job-<to_db>``) so results dispatch per job. ``pages``,
    if given, is {to_db: [page1_rows, page2_rows]} to exercise Link-header pagination.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/idmapping/run"):
            if run_calls is not None:
                run_calls.append(str(request.url))
            if run_status != 200:
                return httpx.Response(run_status, content=b"{}")
            from urllib.parse import parse_qs

            to_db = (parse_qs(request.content.decode()).get("to") or [""])[0]
            return httpx.Response(200, content=json.dumps({"jobId": f"job-{to_db}"}))
        if "/idmapping/status/" in path:
            return httpx.Response(200, content=json.dumps({"jobStatus": status}))
        if "/idmapping/results/" in path:
            to_db = path.rsplit("/job-", 1)[-1]
            if pages and to_db in pages:
                cursor = request.url.params.get("cursor")
                rows = pages[to_db][1] if cursor else pages[to_db][0]
                resp = httpx.Response(200, content=json.dumps({"results": rows}))
                if not cursor:
                    resp.headers["link"] = (
                        f'<https://u/idmapping/results/job-{to_db}?cursor=2>; rel="next"'
                    )
                return resp
            rows = [{"from": g, "to": a} for g, accs in maps.get(to_db, {}).items() for a in accs]
            return httpx.Response(200, content=json.dumps({"results": rows}))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(base_url="https://u", transport=httpx.MockTransport(handler))
    return UniprotApiBackend(client=client)


async def _map(backend, *gene_ids):
    return await backend.fetch(
        MAP_CAP,
        [{"gene.ncbi.id": g} for g in gene_ids],
        requested_outputs=frozenset(
            {"protein.uniprot.accession", "protein.uniprot.mapping.count",
             "protein.uniprot.mapping.records"}
        ),
        groups_to_compute=frozenset(),
    )


async def test_resolve_mapping_orders_reviewed_first():
    backend = _mapping_backend({
        "UniProtKB-Swiss-Prot": {"7157": ["P04637"]},
        "UniProtKB": {"7157": ["A0A087WT22", "P04637", "H2EHT1"]},
    })
    rec = (await _map(backend, "7157"))[0]
    assert rec.found is True
    # reviewed (P04637) leads; the rest follow in API order, de-duplicated.
    assert rec.values["protein.uniprot.accession"] == ["P04637", "A0A087WT22", "H2EHT1"]
    assert rec.values["protein.uniprot.mapping.count"] == 3
    assert rec.values["protein.uniprot.mapping.records"][0] == {"accession": "P04637", "reviewed": True}
    assert rec.values["protein.uniprot.mapping.records"][1]["reviewed"] is False


async def test_resolve_mapping_falls_back_to_unreviewed_only():
    # A non-model gene with no reviewed entry still resolves from the full UniProtKB job.
    backend = _mapping_backend({
        "UniProtKB-Swiss-Prot": {},
        "UniProtKB": {"403869": ["A0A8I3Q4A6", "E7FIY6"]},
    })
    rec = (await _map(backend, "403869"))[0]
    assert rec.values["protein.uniprot.accession"] == ["A0A8I3Q4A6", "E7FIY6"]
    assert all(r["reviewed"] is False for r in rec.values["protein.uniprot.mapping.records"])


async def test_resolve_mapping_batches_whole_set_in_two_jobs():
    run_calls: list[str] = []
    backend = _mapping_backend(
        {"UniProtKB-Swiss-Prot": {"7157": ["P04637"], "22059": ["P02340"]},
         "UniProtKB": {"7157": ["P04637"], "22059": ["P02340"]}},
        run_calls=run_calls,
    )
    recs = await _map(backend, "7157", "22059")
    # Two jobs total (reviewed + full) for the whole batch — not one per gene.
    assert len(run_calls) == 2
    assert [r.values["protein.uniprot.accession"] for r in recs] == [["P04637"], ["P02340"]]


async def test_resolve_mapping_miss_and_blank():
    backend = _mapping_backend({"UniProtKB-Swiss-Prot": {}, "UniProtKB": {}})
    recs = await _map(backend, "999999", "   ")
    assert recs[0].found is False and recs[0].error is None
    assert recs[1].found is False


async def test_resolve_mapping_all_blank_makes_no_call():
    run_calls: list[str] = []
    backend = _mapping_backend({}, run_calls=run_calls)
    recs = await _map(backend, "", "  ")
    assert all(r.found is False for r in recs) and run_calls == []


async def test_resolve_mapping_job_failure_is_per_query_error():
    backend = _mapping_backend({}, run_status=500)
    recs = await _map(backend, "7157", "22059")
    assert all(r.error is not None and "ID-mapping" in r.error for r in recs)


async def test_resolve_mapping_follows_paginated_results():
    backend = _mapping_backend(
        {"UniProtKB-Swiss-Prot": {"7157": ["P04637"]}},
        pages={"UniProtKB": [[{"from": "7157", "to": "P04637"}],
                             [{"from": "7157", "to": "K7PPA8"}]]},
    )
    rec = (await _map(backend, "7157"))[0]
    # Page 2 (K7PPA8) is reached only by following the Link header.
    assert rec.values["protein.uniprot.accession"] == ["P04637", "K7PPA8"]
