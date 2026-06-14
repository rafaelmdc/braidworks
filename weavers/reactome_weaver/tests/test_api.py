"""Unit tests for the Reactome api backend — dedup, ordering, status mapping.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They
exercise: dedup to distinct pathways, stId ordering, names-cap vs true count, and
400/404/empty/blank/error handling.
"""

from __future__ import annotations

import json

import httpx

from reactome_weaver.backends.api import ReactomeApiBackend

CAP = "resolve_pathways"
ALL = frozenset(
    {
        "pathway.reactome.id",
        "pathway.reactome.names",
        "pathway.reactome.count",
        "pathway.reactome.records",
    }
)


def _pw(st_id, name=None, in_disease=False):
    return {"stId": st_id, "displayName": name or st_id, "isInDisease": in_disease}


def _backend(rows=None, *, status=200, calls=None, limit=30):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status, content=b"{}")
        if request.url.path.endswith("/pathways"):
            return httpx.Response(200, content=json.dumps(rows if rows is not None else []))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(base_url="https://r/ContentService",
                              transport=httpx.MockTransport(handler))
    return ReactomeApiBackend(client=client, limit=limit)


async def _one(backend, accession):
    records = await backend.fetch(
        CAP, [{"protein.uniprot.accession": accession}], requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_dedups_and_orders_by_st_id():
    rows = [_pw("R-HSA-200", "Beta"), _pw("R-HSA-100", "Alpha"), _pw("R-HSA-200", "Beta")]
    v = (await _one(_backend(rows), "P04637")).values
    assert v["pathway.reactome.count"] == 2  # duplicate collapsed
    assert [r["st_id"] for r in v["pathway.reactome.records"]] == ["R-HSA-100", "R-HSA-200"]
    assert v["pathway.reactome.names"] == ["Alpha", "Beta"]
    # the fan dimension: every distinct stId, deduped and ordered
    assert v["pathway.reactome.id"] == ["R-HSA-100", "R-HSA-200"]


async def test_id_set_is_full_while_names_are_capped():
    rows = [_pw(f"R-HSA-{i:03d}") for i in range(5)]
    v = (await _one(_backend(rows, limit=2), "P04637")).values
    # names/records are the top-N display; the id fan dimension is the full set.
    assert len(v["pathway.reactome.names"]) == 2
    assert v["pathway.reactome.id"] == [f"R-HSA-{i:03d}" for i in range(5)]


async def test_names_capped_but_count_is_true_total():
    rows = [_pw(f"R-HSA-{i:03d}") for i in range(5)]
    v = (await _one(_backend(rows, limit=2), "P04637")).values
    assert len(v["pathway.reactome.names"]) == 2
    assert v["pathway.reactome.count"] == 5


async def test_in_disease_flag_carried():
    v = (await _one(_backend([_pw("R-HSA-1", "X", in_disease=True)]), "P04637")).values
    assert v["pathway.reactome.records"][0]["in_disease"] is True


async def test_400_and_404_are_misses():
    for status in (400, 404):
        record = await _one(_backend(status=status), "bad")
        assert record.found is False and record.error is None


async def test_empty_list_is_a_miss():
    record = await _one(_backend([]), "P99999")
    assert record.found is False and record.error is None


async def test_blank_accession_makes_no_call():
    calls: list[str] = []
    record = await _one(_backend(calls=calls), "   ")
    assert record.found is False and record.error is None and calls == []


async def test_server_error_becomes_per_entity_error():
    record = await _one(_backend(status=500), "P04637")
    assert record.found is False and record.error is not None and "Reactome" in record.error


def test_fingerprint_is_stable_and_real():
    fp = ReactomeApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp
