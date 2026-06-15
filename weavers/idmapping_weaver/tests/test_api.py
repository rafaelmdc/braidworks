"""Unit tests for the ID-mapping api backend — the novel async/batch engine.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They exercise:
reviewed-first ordering, the unreviewed fallback, single-batch-not-per-id, Link-header
pagination, the out-of-hub single-job path, misses/blanks, and per-query error handling.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx

from idmapping_weaver.backends.api import IdMappingApiBackend
from idmapping_weaver.edges import Edge

ACC = "protein.uniprot.accession"
COUNT = "protein.uniprot.mapping.count"
RECORDS = "protein.uniprot.mapping.records"
OUTPUTS = frozenset({ACC, COUNT, RECORDS})


def _backend(maps, *, run_calls=None, status="FINISHED", run_status=200, pages=None):
    """A backend serving the ID-mapping flow from ``maps`` = {to_db: {src_id: [target, ...]}}.

    Job ids encode the target db (``job-<to_db>``) so results dispatch per job. ``pages``,
    if given, is {to_db: [page1_rows, page2_rows]} to exercise Link-header pagination.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/idmapping/run"):
            if run_calls is not None:
                run_calls.append(parse_qs(request.content.decode()))
            if run_status != 200:
                return httpx.Response(run_status, content=b"{}")
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
            rows = [{"from": s, "to": t} for s, ts in maps.get(to_db, {}).items() for t in ts]
            return httpx.Response(200, content=json.dumps({"results": rows}))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(base_url="https://u", transport=httpx.MockTransport(handler))
    return IdMappingApiBackend(client=client)


def _edge(into_hub=True, capability="map_geneid", from_db="GeneID", to_db="UniProtKB",
          consumes="gene.ncbi.id", produces=ACC):
    return Edge(capability, from_db, to_db, consumes, produces, into_hub)


async def _run(backend, edge, *ids):
    # Drive the engine directly so tests can use ad-hoc edges without touching the
    # module-level dispatch table; fetch()'s capability->edge lookup is covered by golden.
    return await backend._resolve_edge(edge, [{edge.consumes: i} for i in ids])


async def test_into_hub_orders_reviewed_first():
    edge = _edge()
    backend = _backend({
        "UniProtKB-Swiss-Prot": {"7157": ["P04637"]},
        "UniProtKB": {"7157": ["A0A087WT22", "P04637", "H2EHT1"]},
    })
    rec = (await _run(backend, edge, "7157"))[0]
    assert rec.found is True
    assert rec.values[ACC] == ["P04637", "A0A087WT22", "H2EHT1"]  # reviewed leads
    assert rec.values[COUNT] == 3
    assert rec.values[RECORDS][0] == {"id": "P04637", "reviewed": True}
    assert rec.values[RECORDS][1]["reviewed"] is False


async def test_into_hub_falls_back_to_unreviewed_only():
    edge = _edge()
    backend = _backend({
        "UniProtKB-Swiss-Prot": {},
        "UniProtKB": {"403869": ["A0A8I3Q4A6", "E7FIY6"]},
    })
    rec = (await _run(backend, edge, "403869"))[0]
    assert rec.values[ACC] == ["A0A8I3Q4A6", "E7FIY6"]
    assert all(r["reviewed"] is False for r in rec.values[RECORDS])


async def test_into_hub_runs_two_jobs_for_whole_batch():
    edge = _edge()
    run_calls: list = []
    backend = _backend(
        {"UniProtKB-Swiss-Prot": {"7157": ["P04637"], "22059": ["P02340"]},
         "UniProtKB": {"7157": ["P04637"], "22059": ["P02340"]}},
        run_calls=run_calls,
    )
    recs = await _run(backend, edge, "7157", "22059")
    assert len(run_calls) == 2  # reviewed + full, for the whole batch (not per id)
    assert [r.values[ACC] for r in recs] == [["P04637"], ["P02340"]]


async def test_out_of_hub_single_job():
    # An out-of-hub edge (future batch) runs ONE job, not the reviewed-first pair.
    edge = _edge(into_hub=False, capability="map_to_kegg", from_db="UniProtKB_AC-ID",
                 to_db="KEGG", consumes=ACC, produces="pathway.kegg.id")
    run_calls: list = []
    backend = _backend({"KEGG": {"P04637": ["hsa:7157"]}}, run_calls=run_calls)
    rec = (await _run(backend, edge, "P04637"))[0]
    assert len(run_calls) == 1 and run_calls[0]["to"] == ["KEGG"]  # single job, no Swiss-Prot
    assert rec.values["pathway.kegg.id"] == ["hsa:7157"]


async def test_miss_and_blank():
    edge = _edge()
    backend = _backend({"UniProtKB-Swiss-Prot": {}, "UniProtKB": {}})
    recs = await _run(backend, edge, "999999", "   ")
    assert recs[0].found is False and recs[0].error is None
    assert recs[1].found is False


async def test_all_blank_makes_no_call():
    edge = _edge()
    run_calls: list = []
    backend = _backend({}, run_calls=run_calls)
    recs = await _run(backend, edge, "", "  ")
    assert all(r.found is False for r in recs) and run_calls == []


async def test_job_failure_is_per_query_error():
    edge = _edge()
    backend = _backend({}, run_status=500)
    recs = await _run(backend, edge, "7157", "22059")
    assert all(r.error is not None and "ID-mapping" in r.error for r in recs)


async def test_follows_paginated_results():
    edge = _edge()
    backend = _backend(
        {"UniProtKB-Swiss-Prot": {"7157": ["P04637"]}},
        pages={"UniProtKB": [[{"from": "7157", "to": "P04637"}],
                             [{"from": "7157", "to": "K7PPA8"}]]},
    )
    rec = (await _run(backend, edge, "7157"))[0]
    assert rec.values[ACC] == ["P04637", "K7PPA8"]  # page 2 reached via Link header


def test_fingerprint_is_stable_and_real():
    fp = IdMappingApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp
