"""The local backend for gtdb_weaver — the authoritative NCBI→GTDB crosswalk.

Serves lookups from a small SQLite crosswalk (``taxonomy.build_crosswalk_db``)
built from GTDB metadata (bac120 + ar53). Dispatches on whichever input strand is
present: an NCBI taxid (authoritative) or a GTDB species name. Not configured until
the crosswalk DB exists on disk — the introspection builder points it at the default
path without building, so the manifest is complete while goldens skip until a DB is
wired (the fixture builder wires the bundled fixture crosswalk).

Two capabilities:
  - ``describe_gtdb_taxonomy`` — GTDB id + lineage from the crosswalk.
  - ``describe_gtdb_tree_placement`` — the organism's ``gtdb.tree.rootpath`` on the
    GTDB reference tree, for consumers computing patristic distance. Needs the tree
    files too; without them these queries simply miss (the crosswalk lookups still work).

Guide: weaverkit/docs/implementing-backends.md
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from braidworks.core import BackendBase, BackendConfigurationError, LookupRecord
from braidworks.core.source_identity import SourceBinding

from gtdb_weaver import taxonomy, tree
from gtdb_weaver.releases import file_hash

_TREE_PLACEMENT = "describe_gtdb_tree_placement"


class GtdbLocalBackend(BackendBase):
    """local backend — NCBI-taxid / species-name -> GTDB via the crosswalk SQLite."""

    name = "local"

    def __init__(
        self,
        db_path: str | Path | None = None,
        tree_paths: list[str | Path] | None = None,
    ) -> None:
        # ``None`` means "the default DB path, present-or-not" (introspection form).
        self._db_path = Path(db_path) if db_path is not None else _default_db_path()
        self._tree_paths = [Path(p) for p in (tree_paths or [])]
        self._source = SourceBinding(
            self._db_path,
            lambda con: dict(con.execute("SELECT key, value FROM meta")),
            components=tuple(self._tree_paths),
        )
        self._rootpaths: tree._RootPathIndex | None = None  # lazy, cached per instance

    def is_configured(self) -> bool:
        return self._db_path.exists() and self._db_path.stat().st_size > 0

    def fingerprint(self) -> str:
        return self._source.fingerprint() if self.is_configured() else "gtdb-local-none"

    def _reference_rootpaths(self, con: Any) -> tree._RootPathIndex:
        """Leaf-accession → root path for the wired reference tree(s); {} if none present."""
        if self._rootpaths is None:
            row = con.execute("SELECT value FROM meta WHERE key='source_bundle'").fetchone()
            if row:
                bundle = json.loads(row[0])
                if bundle.get("kind") == "official-release":
                    expected = {
                        r["md5"]
                        for label, r in bundle["resources"].items()
                        if label.endswith("_tree")
                    }
                    if any(
                        not path.exists() or file_hash(path, "md5") not in expected
                        for path in self._tree_paths
                    ):
                        raise BackendConfigurationError(
                            "GTDB trees do not match the crosswalk release/checksum bundle"
                        )
            texts = (p.read_text(encoding="utf-8") for p in self._tree_paths if p.exists())
            self._rootpaths = tree.load_rootpath_index(texts)
        return self._rootpaths

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        return await asyncio.to_thread(self._fetch_sync, capability_id, queries)

    def _fetch_sync(self, capability_id: str, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        with self._source.session() as con:
            if capability_id == _TREE_PLACEMENT:
                return self._fetch_tree_placement(con, queries)
            return self._fetch_taxonomy(con, queries)

    def _fetch_taxonomy(self, con: Any, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        records: list[LookupRecord] = []
        for query in queries:  # one record per query, in order — never reorder/drop
            try:
                gtdb_taxonomy = taxonomy.lookup(con, query)
            except taxonomy.AmbiguousClassification as exc:
                records.append(LookupRecord(query=query, error=str(exc)))
                continue
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

    def _fetch_tree_placement(self, con: Any, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        rootpaths = self._reference_rootpaths(con)
        records: list[LookupRecord] = []
        for query in queries:  # one record per query, in order — never reorder/drop
            try:
                accession = taxonomy.rep_accession(con, query)
            except taxonomy.AmbiguousClassification as exc:
                records.append(LookupRecord(query=query, error=str(exc)))
                continue
            path = rootpaths.path_for(accession) if accession else None
            if not path:  # unknown organism, or its species' leaf isn't in the tree
                records.append(LookupRecord(query=query, found=False))
                continue
            records.append(
                LookupRecord(
                    query=query,
                    found=True,
                    values={"gtdb.tree.rootpath": [list(step) for step in path]},
                )
            )
        return records


def _default_db_path() -> Path:
    """Per-user default crosswalk DB path (matches ``setup.default_db_path``)."""
    from gtdb_weaver.setup import default_db_path

    return default_db_path()
