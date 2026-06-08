"""LocalTaxonomyBackend — wraps the SQLite TaxonomyResolverService.

One service per thread (``threading.local``), lazily created; sync calls are run
off the event loop with ``asyncio.to_thread``. Construction is cheap and never
raises: ``is_configured()`` reports whether the DB is present and built, and the
persistent connection is created lazily on first use.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

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
        self._tl = threading.local()
        self._fingerprint: str | None = None
        self._configured = db_is_valid(self._db_path)

    def is_configured(self) -> bool:
        """Whether the taxonomy DB is present and built (checked at construction)."""
        return self._configured

    def _service(self) -> TaxonomyResolverService:
        """Return this thread's resolver service, creating it lazily on first use."""
        svc = getattr(self._tl, "svc", None)
        if svc is None:
            svc = TaxonomyResolverService(self._db_path, self._cache_db_path)
            self._tl.svc = svc
        return svc

    def fingerprint(self) -> str:
        """The taxonomy build version backing this DB (the cache fingerprint)."""
        if self._fingerprint is None:
            info = self._service().get_taxonomy_build_info()
            self._fingerprint = info.get("taxonomy_build_version") or "unversioned"
        return self._fingerprint

    async def resolve(
        self, capability_id: str, queries: list, *, need_lineage: bool
    ) -> list[TaxonMatch]:
        """Resolve a batch off the event loop (one resolver call per batch)."""
        return await asyncio.to_thread(
            self._resolve_sync, capability_id, list(queries), need_lineage
        )

    # --- sync worker (runs in a thread) ------------------------------------

    def _resolve_sync(
        self, capability_id: str, queries: list, need_lineage: bool
    ) -> list[TaxonMatch]:
        svc = self._service()
        if capability_id == vocab.RESOLVE_NAME:
            req = BatchResolveRequest(items=[ResolveRequest(original_name=str(q)) for q in queries])
            results = svc.resolve_batch(req).results
            return [self._name_match(q, r, need_lineage, svc) for q, r in zip(queries, results)]
        if capability_id == vocab.RESOLVE_TAXID:
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
