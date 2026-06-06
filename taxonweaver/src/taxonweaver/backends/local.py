"""LocalTaxonomyBackend — wraps the SQLite TaxonomyResolverService.

One service per thread (``threading.local``), lazily created; sync calls are run
off the event loop with ``asyncio.to_thread``. The DB path is validated at
construction (``BackendConfigurationError``), but the persistent connection is
created lazily on first use.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path

from taxonomy_resolver.policy import ResolutionStatus
from taxonomy_resolver.schemas import BatchResolveRequest, ResolveRequest, ResolveResult
from taxonomy_resolver.service import TaxonomyResolverService

from braidworks.core import BackendConfigurationError

from .. import vocab
from ..intermediate import CandidateMatch, LineageEntry, TaxonMatch, TaxonMatchStatus

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
        self._db_path = Path(db_path)
        self._cache_db_path = Path(cache_db_path) if cache_db_path else None
        self._tl = threading.local()
        self._fingerprint: str | None = None
        self._validate()

    def _validate(self) -> None:
        if not self._db_path.exists():
            raise BackendConfigurationError(
                f"taxonomy db not found: {self._db_path}\n"
                "Create it with `taxon-weaver ensure`, or pass auto_setup=True to "
                "build_ncbi_weaver(...), or set BRAIDWORKS_AUTO_DOWNLOAD=1."
            )
        try:
            con = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
            try:
                con.execute("SELECT 1 FROM sqlite_master LIMIT 1")
            finally:
                con.close()
        except sqlite3.Error as exc:
            raise BackendConfigurationError(f"invalid taxonomy db {self._db_path}: {exc}") from exc

    def is_configured(self) -> bool:
        """Always true once constructed — the DB path was validated in ``__init__``."""
        return True

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
                c.taxid, c.name, c.rank, c.score, str(c.match_type), c.lineage,
            )
        else:
            taxid, name, rank, score, mtype, inline = (
                r.matched_taxid, r.matched_name, r.matched_rank,
                r.score, str(r.match_type), r.lineage,
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
