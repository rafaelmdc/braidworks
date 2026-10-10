"""The local backend for disbiome_weaver.

Serves microbe→disease lookups from the small SQLite built by ``setup.py`` (one
row per Disbiome experiment, keyed by exact NCBI taxid). Summary queries aggregate
indexed light columns; compact queries read projected columns. Full JSON is parsed
only for the full group. Distinct inputs share work within one batch:

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
from copy import deepcopy
from dataclasses import replace
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
        "experiment_id": _coerce_taxid(record.get("experiment_id")),
        "publication_id": _coerce_taxid(record.get("publication_id")),
        "organism_id": _coerce_taxid(record.get("organism_id")),
        "disease_id": _coerce_taxid(record.get("disease_id")),
        "disease_name": record.get("disease_name"),
        "meddra_id": record.get("meddra_id"),
        "meddra_level": record.get("meddra_level"),
        "direction": record.get("qualitative_outcome"),
        "sample": record.get("sample_name"),
        "host": record.get("host_type"),
        "method": record.get("method_name"),
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
        options = params or {}
        if any(not isinstance(value, str) or not value for value in options.values()):
            return [
                LookupRecord(query=q, error="Disbiome filters must be nonempty strings")
                for q in queries
            ]
        if options:
            return await asyncio.to_thread(self._lookup_all, queries, groups_to_compute, options)
        return await asyncio.to_thread(self._lookup_all, queries, groups_to_compute)

    def _lookup_all(
        self,
        queries: list[dict[str, Any]],
        groups: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        # Per-call work reuse, bounded by this batch; results remain detached.
        with self._source.session() as con:
            resolved: dict[int | None, LookupRecord] = {}
            records = []
            for query in queries:
                # A generic identity is authoritative when both alternatives occur.
                # Never fall back to a different species/ancestor after an exact miss.
                key = (
                    "ncbi.taxon.id"
                    if query.get("ncbi.taxon.id") is not None
                    else "ncbi.taxon.species_id"
                )
                taxid = _coerce_taxid(query.get(key))
                if taxid not in resolved:
                    resolved[taxid] = self._lookup_one(con, query, taxid, groups, params)
                records.append(
                    replace(resolved[taxid], query=query, values=deepcopy(resolved[taxid].values))
                )
            return records

    def _lookup_one(
        self,
        con: sqlite3.Connection,
        query: dict[str, Any],
        taxid: int | None,
        groups: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> LookupRecord:
        if taxid is None:
            return LookupRecord(query=query, found=False)
        filters = params or {}
        columns = {
            "sample": "sample_name",
            "method": "method_name",
            "outcome": "qualitative_outcome",
        }
        where = "ncbi_id = ?"
        bindings = [taxid]
        for name, column in columns.items():
            if name in filters:
                where += f" AND {column} = ?"
                bindings.append(filters[name])
        values: dict[str, Any] = {}
        if "full" in groups:
            rows = con.execute(
                f"SELECT full_json FROM association WHERE {where} ORDER BY experiment_id",
                bindings,
            ).fetchall()
            records = [json.loads(row[0]) for row in rows]
            if not records:
                return LookupRecord(query=query, found=False)
            values[RECORDS] = records
            if "summary" in groups:
                values.update(
                    {
                        NAMES: sorted(
                            {r["disease_name"] for r in records if r.get("disease_name")}
                        ),
                        COUNT: len(records),
                    }
                )
            if "associations" in groups:
                values[ASSOCIATIONS] = [_association_row(record) for record in records]
        elif "associations" in groups:
            rows = con.execute(
                "SELECT experiment_id, publication_id, organism_id, disease_id, disease_name, meddra_id, meddra_level, qualitative_outcome, sample_name, host_type, method_name "
                f"FROM association WHERE {where} ORDER BY experiment_id",
                bindings,
            ).fetchall()
            if not rows:
                return LookupRecord(query=query, found=False)
            keys = (
                "experiment_id",
                "publication_id",
                "organism_id",
                "disease_id",
                "disease_name",
                "meddra_id",
                "meddra_level",
                "qualitative_outcome",
                "sample_name",
                "host_type",
                "method_name",
            )
            records = [dict(zip(keys, row)) for row in rows]
            values[ASSOCIATIONS] = [_association_row(record) for record in records]
            if "summary" in groups:
                values.update(
                    {
                        NAMES: sorted(
                            {r["disease_name"] for r in records if r.get("disease_name")}
                        ),
                        COUNT: len(records),
                    }
                )
        elif "summary" in groups:
            rows = con.execute(
                f"SELECT disease_name, COUNT(*) FROM association WHERE {where} GROUP BY disease_name",
                bindings,
            ).fetchall()
            if not rows:
                return LookupRecord(query=query, found=False)
            values.update(
                {
                    NAMES: sorted(row[0] for row in rows if row[0]),
                    COUNT: sum(row[1] for row in rows),
                }
            )
        elif not con.execute(
            f"SELECT 1 FROM association WHERE {where} LIMIT 1", bindings
        ).fetchone():
            return LookupRecord(query=query, found=False)
        if "coverage" in groups:
            # Rank is source evidence, never inferred from the caller's input key.
            rows = con.execute(
                f"SELECT full_json FROM association WHERE {where} ORDER BY experiment_id",
                bindings,
            ).fetchall()
            organisms = []
            for row in rows:
                record = json.loads(row[0])
                organism = record.get("organism") or {}
                identity = {
                    "taxid": _coerce_taxid(record.get("organism_ncbi_id")),
                    "organism_id": _coerce_taxid(record.get("organism_id")),
                    "name": organism.get("scientific_name") or organism.get("name"),
                    "rank": organism.get("rank"),
                }
                if identity not in organisms:
                    organisms.append(identity)
            values["microbe.disease.coverage"] = {
                "matched_taxid": taxid,
                "lookup_policy": "exact",
                "ancestor_rollup": False,
                "propagated_to_descendants": False,
                "organisms": organisms,
                "rank_available": all(item["rank"] is not None for item in organisms),
                "experiment_count": len(rows),
            }
        return LookupRecord(query=query, found=True, values=values)
