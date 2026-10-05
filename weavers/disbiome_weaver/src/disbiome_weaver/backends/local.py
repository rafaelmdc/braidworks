"""The local backend for disbiome_weaver.

Serves microbe→disease lookups from the small SQLite built by ``setup.py`` (one
row per Disbiome experiment, keyed by NCBI taxid). A single indexed query returns
every experiment for a taxid; from those rows the backend fills all produced
outputs and the shared mapper emits only the requested slice:

- ``microbe.disease.names``        — distinct disease names (summary)
- ``microbe.disease.count``        — number of experiment records (summary)
- ``microbe.disease.associations`` — one compact row per experiment (associations)
- ``microbe.disease.records``      — the complete joined blob per experiment (full)

The DB is tiny, but queries still run via ``asyncio.to_thread`` so SQLite never
blocks the event loop, with one read-only connection per thread.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from braidworks.core import BackendBase, LookupRecord
from braidworks.core.source_identity import SourceBinding

from disbiome_weaver.setup import _coerce_taxid, db_is_valid, default_disbiome_db_path

NAMES = "microbe.disease.names"
COUNT = "microbe.disease.count"
ASSOCIATIONS = "microbe.disease.associations"
RECORDS = "microbe.disease.records"


def _association_row(record: dict[str, Any]) -> dict[str, Any]:
    """The compact per-experiment view (the association signal + minimal context)."""
    return {
        "disease_name": record.get("disease_name"),
        "meddra_id": record.get("meddra_id"),
        "meddra_level": record.get("meddra_level"),
        "direction": record.get("qualitative_outcome"),
        "sample": record.get("sample_name"),
        "host": record.get("host_type"),
        "method": record.get("method_name"),
    }


def _values_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Fill every produced output from a taxid's experiment records (mapper filters)."""
    names = sorted({r["disease_name"] for r in records if r.get("disease_name")})
    return {
        NAMES: names,
        COUNT: len(records),
        ASSOCIATIONS: [_association_row(r) for r in records],
        RECORDS: records,
    }


class DisbiomeLocalBackend(BackendBase):
    """local backend reading the built Disbiome SQLite."""

    name = "local"

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_disbiome_db_path()
        self._configured = db_is_valid(self._db_path)
        self._fingerprint: str | None = None
        self._source = SourceBinding(
            self._db_path, lambda con: dict(con.execute("SELECT key, value FROM meta"))
        )

    def is_configured(self) -> bool:
        return self._configured

    def fingerprint(self) -> str:
        if not self._configured:
            return "unconfigured:local"
        return self._source.fingerprint()

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        return await asyncio.to_thread(self._lookup_all, queries)

    def _lookup_all(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        with self._source.session() as con:
            return [self._lookup_one(con, q) for q in queries]

    def _lookup_one(self, con: sqlite3.Connection, query: dict[str, Any]) -> LookupRecord:
        taxid = _coerce_taxid(query.get("ncbi.taxon.species_id"))
        if taxid is None:
            return LookupRecord(query=query, found=False)
        rows = con.execute(
            "SELECT full_json FROM association WHERE ncbi_id = ? ORDER BY experiment_id",
            (taxid,),
        ).fetchall()
        if not rows:
            return LookupRecord(query=query, found=False)
        records = [json.loads(r[0]) for r in rows]
        return LookupRecord(query=query, found=True, values=_values_from_records(records))
