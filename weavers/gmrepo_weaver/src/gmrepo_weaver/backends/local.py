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
import sqlite3
import threading
from pathlib import Path
from typing import Any

from braidworks.core import BackendBase, LookupRecord

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


def _values(overview: dict[str, Any] | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fill every produced output from a taxid's overview + association rows."""
    names = sorted({r["phenotype_name"] for r in rows if r.get("phenotype_name")})
    associations = [_association_row(r) for r in rows]
    return {
        OVERVIEW: overview,
        NAMES: names,
        COUNT: len(rows),
        ASSOCIATIONS: associations,
        RECORDS: {"overview": overview, "associations": rows},
    }


class GmrepoLocalBackend(BackendBase):
    """local backend reading the built GMrepo SQLite."""

    name = "local"

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_gmrepo_db_path()
        self._configured = db_is_valid(self._db_path)
        self._fingerprint: str | None = None
        self._local = threading.local()

    def is_configured(self) -> bool:
        return self._configured

    def fingerprint(self) -> str:
        # GMrepo has no release tag; the build records a content hash of the fetched
        # tables. Read it once (only ever called when configured).
        if self._fingerprint is None:
            row = (
                self._connect()
                .execute("SELECT value FROM meta WHERE key = 'content_sha256'")
                .fetchone()
            )
            self._fingerprint = f"gmrepo-{row[0][:16]}" if row else "unconfigured:local"
        return self._fingerprint

    def _connect(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(
                f"file:{self._db_path}?mode=ro", uri=True, check_same_thread=False
            )
            con.row_factory = sqlite3.Row
            self._local.con = con
        return con

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
            return await asyncio.to_thread(self._profiles_all, queries)
        return await asyncio.to_thread(self._lookup_all, queries)

    def _lookup_all(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        con = self._connect()
        return [self._lookup_one(con, q) for q in queries]

    def _profiles_all(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        con = self._connect()
        return [self._profiles_one(con, q) for q in queries]

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
                "FROM sample_profile WHERE mesh_id = ? ORDER BY run_id, ncbi_taxon_id",
                (mesh_id,),
            ).fetchall()
        ]
        if not rows:
            return LookupRecord(query=query, found=False)
        n_runs = len({r["run_id"] for r in rows})
        return LookupRecord(
            query=query,
            found=True,
            values={SAMPLE_PROFILES: {"mesh_id": mesh_id, "n_runs": n_runs, "profiles": rows}},
        )

    def _lookup_one(self, con: sqlite3.Connection, query: dict[str, Any]) -> LookupRecord:
        taxid = _coerce_taxid(query.get("ncbi.taxon.id"))
        if taxid is None:
            return LookupRecord(query=query, found=False)
        rows = [
            dict(r)
            for r in con.execute(
                "SELECT rank, mesh_id, phenotype_name, samples, phenotype_valid_runs, "
                "prevalence_percentage, abundance_mean, abundance_median, abundance_sd "
                "FROM association WHERE ncbi_taxon_id = ? ORDER BY mesh_id",
                (taxid,),
            ).fetchall()
        ]
        overview_row = con.execute(
            "SELECT rank, name, pct_of_all_samples, nr_phenotypes, presented_samples "
            "FROM overview WHERE ncbi_taxon_id = ? ORDER BY rank LIMIT 1",
            (taxid,),
        ).fetchone()
        overview = dict(overview_row) if overview_row is not None else None
        if not rows and overview is None:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_values(overview, rows))
