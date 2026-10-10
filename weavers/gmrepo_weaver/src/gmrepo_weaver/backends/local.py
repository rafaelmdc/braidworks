"""The local backend for gmrepo_weaver.

Serves microbe→abundance lookups from the small SQLite built by ``setup.py`` (a
per-taxon global ``overview`` row plus one ``association`` row per phenotype, both
keyed by NCBI taxon id). Two indexed queries per taxid fill all produced outputs;
the shared mapper emits only the requested slice:

- ``microbe.abundance.overview``        — global gut-metagenome summary (summary)
- ``microbe.abundance.phenotype_names`` — distinct phenotype names (summary)
- ``microbe.abundance.count``           — number of phenotype records (summary)
- ``microbe.abundance.associations``    — one compact row per phenotype (associations)
- ``microbe.abundance.records``         — the complete joined blob (full)

The DB is small, but queries still run via ``asyncio.to_thread`` so SQLite never
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

from gmrepo_weaver.setup import _coerce_taxid, db_is_valid, default_gmrepo_db_path

OVERVIEW = "microbe.abundance.overview"
NAMES = "microbe.abundance.phenotype_names"
COUNT = "microbe.abundance.count"
ASSOCIATIONS = "microbe.abundance.associations"
RECORDS = "microbe.abundance.records"
SAMPLE_PROFILES = "microbe.abundance.sample_profiles"

_PROFILES_CAPABILITY = "gmrepo.sample_profiles"


def _association_row(row: dict[str, Any]) -> dict[str, Any]:
    """The compact per-phenotype view (the prevalence + abundance signal)."""
    return {
        "mesh_id": row.get("mesh_id"),
        "phenotype": row.get("phenotype_name"),
        "rank": row.get("rank"),
        "samples": row.get("samples"),
        "prevalence_percentage": row.get("prevalence_percentage"),
        "abundance_mean": row.get("abundance_mean"),
        "abundance_median": row.get("abundance_median"),
        "abundance_sd": row.get("abundance_sd"),
    }


def _acquisition(con: sqlite3.Connection) -> dict[str, Any]:
    row = con.execute("SELECT value FROM meta WHERE key = 'acquisition'").fetchone()
    return json.loads(row[0]) if row else {"scope": "unknown", "taxa": {}, "profiles": {}}


class GmrepoLocalBackend(BackendBase):
    """local backend reading the built GMrepo SQLite."""

    name = "local"

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_gmrepo_db_path()
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
        if capability_id == _PROFILES_CAPABILITY:
            if "metadata" in groups_to_compute:
                return await asyncio.to_thread(self._profiles_all, queries, groups_to_compute)
            return await asyncio.to_thread(self._profiles_all, queries)
        return await asyncio.to_thread(self._lookup_all, queries, groups_to_compute)

    def _lookup_all(
        self, queries: list[dict[str, Any]], groups: frozenset[str]
    ) -> list[LookupRecord]:
        # Legacy direct-backend callers use an empty group set for the full view.
        groups = groups or frozenset({"summary", "associations", "full"})
        with self._source.session() as con:
            return [self._lookup_one(con, q, groups) for q in queries]

    def _profiles_all(
        self, queries: list[dict[str, Any]], groups: frozenset[str] | None = None
    ) -> list[LookupRecord]:
        groups = groups or frozenset({"profiles"})
        with self._source.session() as con:
            records = []
            for query in queries:
                scope = (
                    _acquisition(con)
                    .get("profiles", {})
                    .get(str(query.get("disease.mesh.id", "")).strip())
                )
                if "profiles" in groups:
                    record = self._profiles_one(con, query)
                else:
                    record = (
                        LookupRecord(query=query, found=True)
                        if scope
                        else LookupRecord(query=query, error="GMrepo run metadata not acquired")
                    )
                if "metadata" in groups and record.found:
                    metadata = scope.get("run_metadata") if scope else None
                    record.values["microbe.abundance.run_metadata"] = {
                        "mesh_id": str(query.get("disease.mesh.id", "")).strip(),
                        "records": [dict(metadata[rid]) for rid in sorted(metadata)]
                        if metadata is not None
                        else [],
                        "available": metadata is not None,
                        "coverage": {k: v for k, v in scope.items() if k != "run_metadata"}
                        if scope
                        else None,
                        "selection_scope": "observed run listing before bounded profile acquisition; no additional metadata requests",
                        "interpretation": "provider metadata and units retained; unknown values not inferred",
                    }
                records.append(record)
            return records

    def _profiles_one(self, con: sqlite3.Connection, query: dict[str, Any]) -> LookupRecord:
        mesh_id = query.get("disease.mesh.id")
        mesh_id = str(mesh_id).strip() if mesh_id is not None else None
        if not mesh_id:
            return LookupRecord(query=query, found=False)
        rows = [
            {
                "run_id": r["run_id"],
                "ncbi_taxon_id": r["ncbi_taxon_id"],
                "rank": r["rank"],
                "relative_abundance": r["relative_abundance"],
            }
            for r in con.execute(
                "SELECT run_id, ncbi_taxon_id, rank, relative_abundance "
                "FROM sample_profile WHERE mesh_id = ? ORDER BY run_id, ncbi_taxon_id, rank",
                (mesh_id,),
            ).fetchall()
        ]
        coverage = _acquisition(con).get("profiles", {}).get(mesh_id)
        if coverage is not None:
            coverage = {key: value for key, value in coverage.items() if key != "run_metadata"}
        if coverage is None:
            if not rows:
                return LookupRecord(
                    query=query, error=f"GMrepo profiles not acquired for {mesh_id}"
                )
            coverage = {
                "requested": None,
                "selected_runs": None,
                "fetched_runs": None,
                "empty_runs": None,
                "failed_runs": None,
                "complete": None,
                "scope": "caller-supplied",
                "cohort_total_runs": None,
            }
        if coverage.get("status") == "failed" or (coverage.get("failed_runs", 0) and not rows):
            return LookupRecord(
                query=query, error=f"GMrepo profile acquisition incomplete: {coverage}"
            )
        n_runs = len({r["run_id"] for r in rows})
        return LookupRecord(
            query=query,
            found=True,
            values={
                SAMPLE_PROFILES: {
                    "mesh_id": mesh_id,
                    "n_runs": n_runs,
                    "n_runs_with_rows": n_runs,
                    "profiles": rows,
                    "coverage": coverage,
                    "denominator": {
                        "fetched_runs": coverage.get("fetched_runs"),
                        "cohort_total_runs": coverage.get("cohort_total_runs"),
                    },
                }
            },
            warnings=(
                (
                    "GMrepo n_runs counts runs with retained rows; use coverage and "
                    "denominator to assess empty, failed and capped acquisition."
                ),
            ),
        )

    def _lookup_one(
        self, con: sqlite3.Connection, query: dict[str, Any], groups: frozenset[str]
    ) -> LookupRecord:
        taxid = _coerce_taxid(query.get("ncbi.taxon.id"))
        if taxid is None:
            return LookupRecord(query=query, found=False)
        coverage = _acquisition(con).get("taxa", {}).get(str(taxid))
        if coverage and coverage.get("status") == "failed":
            return LookupRecord(
                query=query, error=f"GMrepo taxon acquisition failed: {coverage.get('error')}"
            )
        want_rows = bool(groups & {"full", "associations"})
        rows = []
        summary_rows = []
        if want_rows:
            rows = [
                dict(r)
                for r in con.execute(
                    "SELECT rank, mesh_id, phenotype_name, samples, phenotype_valid_runs, "
                    "prevalence_percentage, abundance_mean, abundance_median, abundance_sd "
                    "FROM association WHERE ncbi_taxon_id = ? ORDER BY mesh_id, rank",
                    (taxid,),
                ).fetchall()
            ]
        else:
            summary_rows = con.execute(
                "SELECT phenotype_name, COUNT(*) FROM association "
                "WHERE ncbi_taxon_id = ? GROUP BY phenotype_name",
                (taxid,),
            ).fetchall()
        overview_row = con.execute(
            "SELECT rank, name, pct_of_all_samples, nr_phenotypes, presented_samples "
            "FROM overview WHERE ncbi_taxon_id = ? ORDER BY rank LIMIT 1",
            (taxid,),
        ).fetchone()
        overview = dict(overview_row) if overview_row is not None else None
        count = len(rows) if want_rows else sum(row[1] for row in summary_rows)
        if not count and overview is None:
            return LookupRecord(query=query, found=False)
        values = {}
        if "summary" in groups:
            values.update(
                {
                    OVERVIEW: overview,
                    NAMES: sorted({r["phenotype_name"] for r in rows if r.get("phenotype_name")})
                    if want_rows
                    else sorted(row[0] for row in summary_rows if row[0]),
                    COUNT: count,
                }
            )
        if "associations" in groups:
            values[ASSOCIATIONS] = [_association_row(row) for row in rows]
        if "full" in groups:
            values[RECORDS] = {"overview": overview, "associations": rows}
        scope = coverage or {"scope": "caller-supplied", "complete": None, "rows": count}
        if "summary" in groups:
            values["microbe.abundance.coverage"] = scope
        if "full" in groups:
            values[RECORDS]["coverage"] = scope
        return LookupRecord(
            query=query,
            found=True,
            values=values,
            warnings=()
            if scope.get("complete")
            else (
                "GMrepo association counts describe retained rows; full acquisition is not established.",
            ),
        )
