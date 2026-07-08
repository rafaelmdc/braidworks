"""The local backend for mondo_weaver.

Serves disease→ontology lookups from the SQLite built by ``setup.py``. Given a MeSH or
MedDRA disease id (per capability), it resolves the unified MONDO id via the ``xref``
index (preferring ``MONDO:equivalentTo`` matches), then fills all produced outputs:

- ``disease.mondo.id``            — the resolved MONDO id (summary/term)
- ``disease.ontology.name``       — the MONDO term name (term)
- ``disease.ontology.parents``    — direct is-a parents (term)
- ``disease.ontology.depth``      — shortest is-a distance to a MONDO root (term)
- ``disease.ontology.ancestors``  — the term + its full is-a ancestor lineage (ancestors)

Ancestors are walked with a recursive query at lookup time (MONDO's is-a is a DAG), so the
DB carries only edges. Queries run via ``asyncio.to_thread`` so SQLite never blocks the loop.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path
from typing import Any

from braidworks.core import BackendBase, LookupRecord

from mondo_weaver.setup import db_is_valid, default_mondo_db_path

MONDO_ID = "disease.mondo.id"
NAME = "disease.ontology.name"
PARENTS = "disease.ontology.parents"
DEPTH = "disease.ontology.depth"
ANCESTORS = "disease.ontology.ancestors"

# capability id -> (consumed type id, xref source tag)
_CAPABILITY_SOURCE = {
    "mondo.lookup_by_mesh": ("disease.mesh.id", "MESH"),
    "mondo.lookup_by_meddra": ("disease.meddra.id", "MedDRA"),
}

_ANCESTORS_SQL = """
WITH RECURSIVE anc(id, depth) AS (
    SELECT ?, 0
    UNION
    SELECT isa.parent, anc.depth + 1 FROM isa JOIN anc ON isa.child = anc.id
)
SELECT anc.id, MIN(anc.depth) AS d, term.name
FROM anc JOIN term ON term.mondo_id = anc.id
GROUP BY anc.id
ORDER BY d, anc.id
"""


def _coerce_id(value: Any) -> str | None:
    """Coerce a consumed disease id (str or int) to a stripped string, else None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


class MondoLocalBackend(BackendBase):
    """local backend reading the built MONDO SQLite."""

    name = "local"

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_mondo_db_path()
        self._configured = db_is_valid(self._db_path)
        self._fingerprint: str | None = None
        self._local = threading.local()

    def is_configured(self) -> bool:
        return self._configured

    def fingerprint(self) -> str:
        # MONDO has a real release tag (OBO data-version); use it as the cache key.
        if self._fingerprint is None:
            row = (
                self._connect()
                .execute("SELECT value FROM meta WHERE key = 'data_version'")
                .fetchone()
            )
            tag = row[0].replace("releases/", "") if row else None
            self._fingerprint = f"mondo-{tag}" if tag else "unconfigured:local"
        return self._fingerprint

    def _connect(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(
                f"file:{self._db_path}?mode=ro", uri=True, check_same_thread=False
            )
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
        return await asyncio.to_thread(self._lookup_all, capability_id, queries)

    def _lookup_all(self, capability_id: str, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        con = self._connect()
        consumed, source = _CAPABILITY_SOURCE[capability_id]
        return [self._lookup_one(con, q, consumed, source) for q in queries]

    def _resolve_mondo(self, con: sqlite3.Connection, source: str, xref_id: str) -> str | None:
        row = con.execute(
            "SELECT mondo_id FROM xref WHERE source = ? AND xref_id = ? "
            "ORDER BY is_equivalent DESC LIMIT 1",
            (source, xref_id),
        ).fetchone()
        return row[0] if row else None

    def _lookup_one(
        self, con: sqlite3.Connection, query: dict[str, Any], consumed: str, source: str
    ) -> LookupRecord:
        xref_id = _coerce_id(query.get(consumed))
        if xref_id is None:
            return LookupRecord(query=query, found=False)
        mondo_id = self._resolve_mondo(con, source, xref_id)
        if mondo_id is None:
            return LookupRecord(query=query, found=False)

        name_row = con.execute("SELECT name FROM term WHERE mondo_id = ?", (mondo_id,)).fetchone()
        lineage = [
            {"mondo_id": rid, "name": rname}
            for rid, _depth, rname in con.execute(_ANCESTORS_SQL, (mondo_id,)).fetchall()
        ]
        parents = [
            {"mondo_id": pid, "name": pname}
            for pid, pname in con.execute(
                "SELECT isa.parent, term.name FROM isa JOIN term ON term.mondo_id = isa.parent "
                "WHERE isa.child = ? ORDER BY isa.parent",
                (mondo_id,),
            ).fetchall()
        ]
        depth = self._depth_to_root(con, mondo_id)
        return LookupRecord(
            query=query,
            found=True,
            values={
                MONDO_ID: mondo_id,
                NAME: name_row[0] if name_row else None,
                PARENTS: parents,
                DEPTH: depth,
                ANCESTORS: lineage,
            },
        )

    def _depth_to_root(self, con: sqlite3.Connection, mondo_id: str) -> int:
        """Shortest is-a distance from ``mondo_id`` to a root (a term with no parents)."""
        rows = con.execute(_ANCESTORS_SQL, (mondo_id,)).fetchall()
        best: int | None = None
        for rid, depth, _name in rows:
            has_parent = con.execute("SELECT 1 FROM isa WHERE child = ? LIMIT 1", (rid,)).fetchone()
            if not has_parent and (best is None or depth < best):
                best = depth
        return best if best is not None else 0
