"""Deterministic, offline stand-ins for gtdb_weaver's backends — for tests/goldens.

Two substrates, both network-free:
  - ``fixture_db_path()`` — builds a tiny crosswalk SQLite from the bundled
    ``data/fixture_crosswalk.tsv`` (5 real GTDB rows), so the *local* backend (which
    the spec's goldens run against) resolves reproducibly.
  - ``mock_client()`` — an ``httpx.AsyncClient`` serving canned ``/search/gtdb``
    responses, so the *api* backend's contract/order tests run offline.

``build_gtdb_weaver_fixture`` (in factory.py) wires both.
"""

from __future__ import annotations

import json
import tempfile
from importlib.resources import files
from pathlib import Path

import httpx

from gtdb_weaver import taxonomy

# Canonical E. coli GTDB taxonomy (the live API's ``; ``-spaced form) — the one
# name-search response the offline api tests assert against.
_ECOLI_ROW = {
    "accession": "GCA_000005845.2",
    "ncbiOrgName": "Escherichia coli str. K-12 substr. MG1655",
    "ncbiTaxonomy": "d__Bacteria; ...; s__Escherichia coli",
    "gtdbTaxonomy": (
        "d__Bacteria; p__Pseudomonadota; c__Gammaproteobacteria; o__Enterobacterales; "
        "f__Enterobacteriaceae; g__Escherichia; s__Escherichia coli"
    ),
    "isGtdbSpeciesRep": True,
    "isNcbiTypeMaterial": False,
}

# Process-lifetime cache so repeated fixture builds in one run don't rebuild the DB.
_FIXTURE_DB: Path | None = None


def fixture_db_path() -> Path:
    """Build (once per process) the tiny crosswalk SQLite from the bundled TSV."""
    global _FIXTURE_DB
    if _FIXTURE_DB is not None and _FIXTURE_DB.exists():
        return _FIXTURE_DB
    raw = (files("gtdb_weaver") / "data" / "fixture_crosswalk.tsv").read_text(encoding="utf-8")
    rows: list[tuple[int, str, bool]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        taxid, gtdb_taxonomy, is_rep = line.split("\t")
        rows.append((int(taxid), gtdb_taxonomy, is_rep.strip().lower() in {"t", "true", "1"}))
    target = Path(tempfile.mkdtemp(prefix="gtdb_weaver-fixture-")) / "crosswalk.sqlite"
    taxonomy.build_crosswalk_db(rows, target, release="fixture")
    _FIXTURE_DB = target
    return target


def _handler(request: httpx.Request) -> httpx.Response:
    """Canned ``/search/gtdb`` responses: E. coli by name, empty otherwise."""
    if request.url.path.endswith("/search/gtdb"):
        search = (request.url.params.get("search") or "").strip().lower()
        rows = [_ECOLI_ROW] if search == "escherichia coli" else []
        return httpx.Response(200, content=json.dumps({"rows": rows}))
    return httpx.Response(404, content=json.dumps({"detail": "not found"}))


def mock_client() -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` serving the canned responses (no network)."""
    return httpx.AsyncClient(base_url="https://gtdb.test", transport=httpx.MockTransport(_handler))
