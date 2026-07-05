"""The local backend for gtdb_weaver — the authoritative NCBI→GTDB crosswalk.

Serves lookups from a small SQLite crosswalk (``taxonomy.build_crosswalk_db``)
built from GTDB metadata (bac120 + ar53). Dispatches on whichever input strand is
present: an NCBI taxid (authoritative) or a GTDB species name. Not configured until
the crosswalk DB exists on disk — the introspection builder points it at the default
path without building, so the manifest is complete while goldens skip until a DB is
wired (the fixture builder wires the bundled fixture crosswalk).

Guide: weaverkit/docs/implementing-backends.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from braidworks.core import BackendBase
from braidworks.core import LookupRecord

from gtdb_weaver import taxonomy


class GtdbLocalBackend(BackendBase):
    """local backend — NCBI-taxid / species-name -> GTDB via the crosswalk SQLite."""

    name = "local"

    def __init__(self, db_path: str | Path | None = None) -> None:
        # ``None`` means "the default DB path, present-or-not" (introspection form).
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()

    def is_configured(self) -> bool:
        return self._db_path.exists() and self._db_path.stat().st_size > 0

    def fingerprint(self) -> str:
        # The GTDB release recorded at DB build is the source of truth; falls back to
        # a stable non-empty sentinel so conformance never sees "" / "unknown".
        release = taxonomy.db_release(self._db_path) if self.is_configured() else None
        return f"gtdb-local-{release or 'none'}"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        con = taxonomy.open_ro(self._db_path)
        try:
            records: list[LookupRecord] = []
            for query in queries:  # one record per query, in order — never reorder/drop
                gtdb_taxonomy = taxonomy.lookup(con, query)
                if not gtdb_taxonomy:
                    records.append(LookupRecord(query=query, found=False))  # a miss is normal
                    continue
                taxon_id, lineage = taxonomy.parse_gtdb_taxonomy(gtdb_taxonomy)
                records.append(
                    LookupRecord(
                        query=query,
                        found=True,
                        values={"gtdb.taxon.id": taxon_id, "gtdb.lineage": lineage},
                    )
                )
            return records
        finally:
            con.close()


def _default_db_path() -> Path:
    """Per-user default crosswalk DB path (matches ``setup.default_db_path``)."""
    from gtdb_weaver.setup import default_db_path

    return default_db_path()
