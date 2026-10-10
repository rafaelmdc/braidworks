"""LocalTaxonomyBackend — wraps the SQLite TaxonomyResolverService.

One owned service per batch; sync calls are run
off the event loop with ``asyncio.to_thread``. Construction is cheap and never
raises: ``is_configured()`` reports whether the DB is present and built, and the
read session is bound to the backend generation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from braidworks.core import LookupRecord
from braidworks.core.source_identity import SourceBinding
from taxonomy_resolver.policy import ResolutionStatus
from taxonomy_resolver.schemas import BatchResolveRequest, ResolveRequest, ResolveResult
from taxonomy_resolver.service import TaxonomyResolverService

from .. import vocab
from ..intermediate import CandidateMatch, LineageEntry, TaxonMatch, TaxonMatchStatus
from ..setup import db_is_valid

_NEUTRAL_STATUS = {
    ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC: TaxonMatchStatus.RESOLVED,
    ResolutionStatus.RESOLVED_EXACT_SYNONYM: TaxonMatchStatus.RESOLVED,
    ResolutionStatus.RESOLVED_NORMALIZED: TaxonMatchStatus.RESOLVED,
    ResolutionStatus.CONFIRMED_BY_USER: TaxonMatchStatus.RESOLVED,
    ResolutionStatus.LEVEL_CONFLICT: TaxonMatchStatus.RESOLVED,  # match found, needs review
    ResolutionStatus.SUGGESTED_FUZZY_UNIQUE: TaxonMatchStatus.FUZZY_UNIQUE,
    ResolutionStatus.AMBIGUOUS_FUZZY_MULTIPLE: TaxonMatchStatus.AMBIGUOUS,
    ResolutionStatus.MANUAL_REVIEW_REQUIRED: TaxonMatchStatus.AMBIGUOUS,
    ResolutionStatus.UNRESOLVED_NO_MATCH: TaxonMatchStatus.NO_MATCH,
    ResolutionStatus.UNRESOLVED_VAGUE_LABEL: TaxonMatchStatus.NO_MATCH,
    ResolutionStatus.REJECTED_BY_USER: TaxonMatchStatus.NO_MATCH,
}


class LocalTaxonomyBackend:
    """Resolution backend backed by the local SQLite taxonomy database."""

    name = "local"

    def __init__(self, db_path: str | Path, *, cache_db_path: str | Path | None = None) -> None:
        # Backbone contract: construct cheap and never raise for missing data —
        # ``is_configured()`` reports whether the DB is actually present and built.
        # The hard "you asked for local but it's absent" error lives in the
        # configured builder path (``build_ncbi_weaver`` -> ``ensure_taxonomy_db``),
        # not here, so a zero-config introspection build can wire an unconfigured
        # backend (manifest-complete, golden skips) without a 1.2 GB download.
        self._db_path = Path(db_path)
        self._cache_db_path = Path(cache_db_path) if cache_db_path else None
        self._source = SourceBinding(
            self._db_path, lambda con: dict(con.execute("SELECT key, value FROM metadata"))
        )
        self._fingerprint: str | None = None
        self._configured = db_is_valid(self._db_path)

    def is_configured(self) -> bool:
        """Whether the taxonomy DB is present and built (checked at construction)."""
        return self._configured

    def fingerprint(self) -> str:
        if not self._configured:
            return "ncbi-local-unbuilt"
        return self._source.fingerprint()

    async def resolve(
        self, capability_id: str, queries: list, *, need_lineage: bool
    ) -> list[TaxonMatch]:
        """Resolve a batch off the event loop (one resolver call per batch)."""
        return await asyncio.to_thread(
            self._resolve_sync, capability_id, list(queries), need_lineage
        )

    async def describe_taxon_history(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        return await asyncio.to_thread(self._history_sync, queries)

    def _history_sync(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        with self._source.session() as con:
            meta = dict(con.execute("SELECT key, value FROM metadata"))
            merged_available = meta.get("merged_history_present") == "true"
            deleted_available = meta.get("deleted_history_present") == "true"
            records = []
            for query in queries:
                raw = query.get(vocab.TAXON_ID)
                try:
                    taxid = int(raw)
                    if isinstance(raw, bool) or taxid < 1 or isinstance(raw, float):
                        raise ValueError("invalid taxid")
                except (TypeError, ValueError):
                    records.append(LookupRecord(query=query, found=False))
                    continue
                chain = [taxid]
                current = taxid
                seen = set()
                error = None
                while merged_available:
                    row = con.execute(
                        "SELECT new_taxid FROM taxon_merged WHERE old_taxid=?", (current,)
                    ).fetchone()
                    if row is None:
                        break
                    if current in seen:
                        error = "Taxonomy history merge cycle"
                        break
                    seen.add(current)
                    current = row[0]
                    chain.append(current)
                if error:
                    records.append(LookupRecord(query=query, error=error))
                    continue
                present = (
                    con.execute("SELECT 1 FROM taxa WHERE taxid=?", (current,)).fetchone()
                    is not None
                )
                deleted = (
                    deleted_available
                    and con.execute(
                        "SELECT 1 FROM taxon_deleted WHERE taxid=?", (current,)
                    ).fetchone()
                    is not None
                )
                status = (
                    ("merged" if len(chain) > 1 else "current")
                    if present
                    else "deleted"
                    if deleted
                    else "unknown"
                )
                records.append(
                    LookupRecord(
                        query=query,
                        found=True,
                        values={
                            "ncbi.taxon.history": {
                                "requested_taxid": taxid,
                                "current_taxid": current if present else None,
                                "status": status,
                                "merge_chain": chain,
                                "history_available": {
                                    "merged": merged_available,
                                    "deleted": deleted_available,
                                },
                                "source_dump_sha256": meta.get("source_dump_sha256"),
                                "build_version": meta.get("taxonomy_build_version"),
                                "interpretation": "dump-scoped identity; deleted/unknown IDs have no inferred successor",
                            }
                        },
                    )
                )
            return records

    # --- sync worker (runs in a thread) ------------------------------------

    def _resolve_sync(
        self, capability_id: str, queries: list, need_lineage: bool
    ) -> list[TaxonMatch]:
        with (
            self._source.session() as connection,
            TaxonomyResolverService(
                self._db_path, self._cache_db_path, taxonomy_connection=connection
            ) as svc,
        ):
            if capability_id == vocab.RESOLVE_NAME:
                req = BatchResolveRequest(
                    items=[ResolveRequest(original_name=str(q)) for q in queries]
                )
                results = svc.resolve_batch(req).results
                return [self._name_match(q, r, need_lineage, svc) for q, r in zip(queries, results)]
            if capability_id == vocab.DESCRIBE_TAXON:
                return [self._taxid_match(q, need_lineage, svc) for q in queries]
            raise ValueError(f"unsupported capability {capability_id!r}")

    def _lineage_for(self, taxid: int, inline, need_lineage: bool, svc: TaxonomyResolverService):
        """Convert/fetch lineage only when needed; never reads the lineage cache for core-only."""
        if not need_lineage or taxid is None:
            return []
        if inline:
            return [LineageEntry(e.taxid, e.rank, e.name) for e in inline]
        return [LineageEntry(d["taxid"], d["rank"], d["name"]) for d in svc.get_lineage(taxid)]

    def _name_match(self, query, r: ResolveResult, need_lineage, svc) -> TaxonMatch:
        status = _NEUTRAL_STATUS[r.status]
        if status is TaxonMatchStatus.FUZZY_UNIQUE and r.candidates:
            c = r.candidates[0]
            taxid, name, rank, score, mtype, inline = (
                c.taxid,
                c.name,
                c.rank,
                c.score,
                str(c.match_type),
                c.lineage,
            )
        else:
            taxid, name, rank, score, mtype, inline = (
                r.matched_taxid,
                r.matched_name,
                r.matched_rank,
                r.score,
                str(r.match_type),
                r.lineage,
            )
        parent = inline[-2].taxid if len(inline) >= 2 else None
        candidates = [
            CandidateMatch(
                taxid=c.taxid,
                name=c.name,
                rank=c.rank,
                match_type=str(c.match_type),
                score=c.score,
                lineage=[LineageEntry(e.taxid, e.rank, e.name) for e in c.lineage],
            )
            for c in r.candidates
        ]
        return TaxonMatch(
            query=query,
            status=status,
            taxid=taxid,
            scientific_name=name,
            rank=rank,
            parent_taxid=parent,
            match_type=mtype,
            score=score,
            requires_review=r.review_required,
            candidates=candidates,
            lineage=self._lineage_for(taxid, inline, need_lineage, svc),
            warnings=[str(w) for w in r.warnings],
        )

    def _taxid_match(self, taxid, need_lineage, svc) -> TaxonMatch:
        try:
            taxid_int = int(taxid)
        except (TypeError, ValueError):
            return TaxonMatch(query=taxid, status=TaxonMatchStatus.NO_MATCH)
        lineage = svc.get_lineage(taxid_int)  # list[dict]; last entry is the taxon itself
        if not lineage:
            return TaxonMatch(query=taxid, status=TaxonMatchStatus.NO_MATCH)
        node = lineage[-1]
        parent = lineage[-2]["taxid"] if len(lineage) >= 2 else None
        entries = (
            [LineageEntry(d["taxid"], d["rank"], d["name"]) for d in lineage]
            if need_lineage
            else []
        )
        return TaxonMatch(
            query=taxid,
            status=TaxonMatchStatus.RESOLVED,
            taxid=taxid_int,
            scientific_name=node["name"],
            rank=node["rank"],
            parent_taxid=parent,
            match_type="taxid",
            score=None,
            lineage=entries,
        )
