"""Unit tests for the PDBe api backend — dedup, best-first ordering, status mapping.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They
exercise: collapsing (structure, chain) rows to distinct structures keeping the best
chain, the coverage/resolution ordering, the ids cap vs true count, the
accession-key-casing fallback, and 404/empty/blank/error handling.
"""

from __future__ import annotations

import json

import httpx

from pdbe_weaver.backends.api import PdbeApiBackend

CAP = "list_structures"
ALL = frozenset(
    {"pdb.id", "structure.pdb.ids", "structure.pdb.count", "structure.pdb.records"}
)


def _row(pid, cov, res=None, chain="A", method="X-ray diffraction"):
    return {"pdb_id": pid, "chain_id": chain, "coverage": cov, "resolution": res,
            "experimental_method": method}


def _backend(mapping=None, *, status=200, limit=25, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status, content=b"{}")
        if "/best_structures/" in request.url.path:
            return httpx.Response(200, content=json.dumps(mapping or {}))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(base_url="https://p/api", transport=httpx.MockTransport(handler))
    return PdbeApiBackend(client=client, limit=limit)


async def _one(backend, accession):
    records = await backend.fetch(
        CAP, [{"protein.uniprot.accession": accession}], requested_outputs=ALL,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_dedups_chains_and_orders_best_first():
    mapping = {"P04637": [_row("1tup", 0.55, 2.2), _row("1tup", 0.52, 2.2, "B"),
                          _row("2ahi", 0.9, 3.5)]}
    v = (await _one(_backend(mapping), "P04637")).values
    assert v["structure.pdb.count"] == 2  # two chains of 1tup collapsed
    assert v["structure.pdb.ids"] == ["2ahi", "1tup"]  # higher coverage first
    assert v["pdb.id"] == ["2ahi", "1tup"]  # the fan dimension: every distinct id
    rec_1tup = next(r for r in v["structure.pdb.records"] if r["pdb_id"] == "1tup")
    assert rec_1tup["coverage"] == 0.55  # kept the best-covering chain


async def test_resolution_breaks_coverage_ties():
    mapping = {"P04637": [_row("aaaa", 0.8, 3.0), _row("bbbb", 0.8, 1.5)]}
    v = (await _one(_backend(mapping), "P04637")).values
    assert v["structure.pdb.ids"] == ["bbbb", "aaaa"]  # same coverage -> lower resolution first


async def test_ids_capped_but_count_is_true_total():
    mapping = {"P04637": [_row(f"p{i:03d}", 0.5 + i / 100, 2.0) for i in range(5)]}
    v = (await _one(_backend(mapping, limit=2), "P04637")).values
    assert len(v["structure.pdb.ids"]) == 2
    assert v["structure.pdb.count"] == 5
    # the fan dimension is the full distinct set, not the display cap
    assert len(v["pdb.id"]) == 5


async def test_accession_key_casing_fallback():
    # PDBe keys the response by the queried accession; if casing differs, use the sole value.
    mapping = {"p04637": [_row("1tup", 0.9, 2.2)]}
    v = (await _one(_backend(mapping), "P04637")).values
    assert v["structure.pdb.ids"] == ["1tup"]


async def test_404_is_a_miss():
    record = await _one(_backend(status=404), "P99999")
    assert record.found is False and record.error is None


async def test_empty_mapping_is_a_miss():
    record = await _one(_backend({"P04637": []}), "P04637")
    assert record.found is False and record.error is None


async def test_blank_accession_makes_no_call():
    calls: list[str] = []
    record = await _one(_backend({}, calls=calls), "   ")
    assert record.found is False and record.error is None and calls == []


async def test_server_error_becomes_per_entity_error():
    record = await _one(_backend(status=500), "P04637")
    assert record.found is False and record.error is not None and "PDBe" in record.error


# --- describe_structure: one pdb.id -> that structure's detail -------------------------

DESCRIBE = "describe_structure"
DESCRIBE_ALL = frozenset(
    {"structure.pdb.title", "structure.pdb.method", "structure.pdb.release_date",
     "structure.pdb.detail"}
)
_DETAIL_1TUP = {
    "title": "TUMOR SUPPRESSOR P53 COMPLEXED WITH DNA",
    "experimental_method": ["X-ray diffraction"],
    "release_date": "19950711",
    "deposition_date": "19950711",
    "entry_authors": ["Cho, Y.", "Pavletich, N.P."],
}


def _describe_backend(detail=None, *, status=200, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status, content=b"{}")
        if "/pdb/entry/summary/" in request.url.path:
            return httpx.Response(200, content=json.dumps(detail or {}))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(base_url="https://p/api", transport=httpx.MockTransport(handler))
    return PdbeApiBackend(client=client)


async def _describe(backend, pdb_id):
    records = await backend.fetch(
        DESCRIBE, [{"pdb.id": pdb_id}], requested_outputs=DESCRIBE_ALL,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_describe_extracts_summary_fields():
    v = (await _describe(_describe_backend({"1tup": [_DETAIL_1TUP]}), "1tup")).values
    assert v["structure.pdb.title"] == "TUMOR SUPPRESSOR P53 COMPLEXED WITH DNA"
    assert v["structure.pdb.method"] == "X-ray diffraction"  # first of the method list
    assert v["structure.pdb.release_date"] == "19950711"
    detail = v["structure.pdb.detail"]
    assert detail["pdb_id"] == "1tup"
    assert detail["authors"] == ["Cho, Y.", "Pavletich, N.P."]
    assert detail["deposition_date"] == "19950711"


async def test_describe_key_casing_fallback():
    # PDBe keys by the queried id; if casing differs, fall back to the sole value.
    v = (await _describe(_describe_backend({"1TUP": [_DETAIL_1TUP]}), "1tup")).values
    assert v["structure.pdb.title"] == "TUMOR SUPPRESSOR P53 COMPLEXED WITH DNA"


async def test_describe_404_is_a_miss():
    record = await _describe(_describe_backend(status=404), "9zzz")
    assert record.found is False and record.error is None


async def test_describe_empty_is_a_miss():
    record = await _describe(_describe_backend({"1tup": []}), "1tup")
    assert record.found is False and record.error is None


async def test_describe_blank_id_makes_no_call():
    calls: list[str] = []
    record = await _describe(_describe_backend({}, calls=calls), "   ")
    assert record.found is False and record.error is None and calls == []


async def test_describe_server_error_becomes_per_entity_error():
    record = await _describe(_describe_backend(status=500), "1tup")
    assert record.found is False and record.error is not None and "PDBe" in record.error


def test_fingerprint_is_stable_and_real():
    fp = PdbeApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp
