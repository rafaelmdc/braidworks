"""Deterministic lookup layer.

Phase 5 resolves names in a deterministic-first order:

1. exact scientific name
2. exact synonym
3. normalized exact match
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .db import fetch_name_matches
from .lineage import get_lineage_for_taxid, lineage_entries_from_json
from .normalize import normalize_level, normalize_name
from .policy import (
    MatchType,
    ResolutionStatus,
    WarningCode,
    allows_auto_accept,
    apply_level_conflict_policy,
    requires_review,
)
from .schemas import CandidateMatch, ResolveRequest, ResolveResult

DatabaseHandle = sqlite3.Connection | str | Path


def _build_candidate(row: object, match_type: MatchType, db_path: DatabaseHandle) -> CandidateMatch:
    """Convert one SQL row into a review-ready exact candidate."""

    taxid = int(row["taxid"])
    lineage = lineage_entries_from_json(row["lineage_json"])
    return CandidateMatch(
        taxid=taxid,
        name=str(row["scientific_name"] or row["matched_name"]),
        rank=str(row["rank"]),
        match_type=match_type,
        score=1.0,
        lineage=lineage if lineage else get_lineage_for_taxid(db_path, taxid),
    )


def _rank_key(row: object, provided_level: str | None) -> tuple[int, int]:
    """Sort deterministic candidates using soft provided-level alignment only."""

    rank = normalize_level(str(row["rank"]))
    level_matches = int(provided_level is not None and rank == provided_level)
    scientific_preferred = int(str(row["name_class"]) == "scientific name")
    return (level_matches, scientific_preferred)


def _finalize_unique_result(
    request: ResolveRequest,
    row: object,
    *,
    db_path: DatabaseHandle,
    status: ResolutionStatus,
    match_type: MatchType,
    warnings: list[WarningCode] | None = None,
) -> ResolveResult:
    """Assemble the single-match deterministic response."""

    final_status, result_warnings = apply_level_conflict_policy(
        status,
        list(warnings or []),
        provided_level=request.provided_level,
        matched_rank=str(row["rank"]),
    )

    taxid = int(row["taxid"])
    lineage = lineage_entries_from_json(row["lineage_json"])
    return ResolveResult(
        original_name=request.original_name,
        normalized_name=normalize_name(request.original_name),
        provided_level=request.provided_level,
        status=final_status,
        review_required=requires_review(final_status),
        auto_accept=allows_auto_accept(final_status),
        match_type=match_type,
        warnings=result_warnings,
        matched_taxid=taxid,
        matched_name=str(row["scientific_name"] or row["matched_name"]),
        matched_rank=str(row["rank"]),
        score=1.0,
        lineage=lineage if lineage else get_lineage_for_taxid(db_path, taxid),
        metadata={"matched_input_name": str(row["matched_name"])},
    )


def _ambiguous_result(
    request: ResolveRequest,
    rows: list[object],
    *,
    db_path: DatabaseHandle,
    match_type: MatchType,
    warning: WarningCode,
) -> ResolveResult:
    """Return a manual-review result for multiple deterministic candidates."""

    provided_level = normalize_level(request.provided_level)
    sorted_rows = sorted(rows, key=lambda row: _rank_key(row, provided_level), reverse=True)
    candidates = [_build_candidate(row, match_type, db_path) for row in sorted_rows]
    return ResolveResult(
        original_name=request.original_name,
        normalized_name=normalize_name(request.original_name),
        provided_level=request.provided_level,
        status=ResolutionStatus.MANUAL_REVIEW_REQUIRED,
        review_required=requires_review(ResolutionStatus.MANUAL_REVIEW_REQUIRED),
        auto_accept=allows_auto_accept(ResolutionStatus.MANUAL_REVIEW_REQUIRED),
        match_type=match_type,
        warnings=[warning],
        candidates=candidates,
        metadata={"candidate_count": len(candidates)},
    )


def _coalesce_normalized_matches(rows: list[object]) -> list[object]:
    """Prefer one deterministic normalized row per taxid."""

    best_by_taxid: dict[int, object] = {}
    for row in rows:
        taxid = int(row["taxid"])
        existing = best_by_taxid.get(taxid)
        if existing is None:
            best_by_taxid[taxid] = row
            continue
        if str(existing["name_class"]) != "scientific name" and str(row["name_class"]) == "scientific name":
            best_by_taxid[taxid] = row
    return list(best_by_taxid.values())


def resolve_exact(request: ResolveRequest, db_path: DatabaseHandle) -> ResolveResult | None:
    """Return a deterministic result if a safe exact path resolves the input."""

    scientific_rows = fetch_name_matches(
        db_path,
        name_txt=request.original_name,
        scientific_only=True,
    )
    if len(scientific_rows) == 1:
        return _finalize_unique_result(
            request,
            scientific_rows[0],
            db_path=db_path,
            status=ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC,
            match_type=MatchType.EXACT_SCIENTIFIC,
        )
    if len(scientific_rows) > 1:
        return _ambiguous_result(
            request,
            scientific_rows,
            db_path=db_path,
            match_type=MatchType.EXACT_SCIENTIFIC,
            warning=WarningCode.MULTIPLE_EXACT_CANDIDATES,
        )

    synonym_rows = fetch_name_matches(
        db_path,
        name_txt=request.original_name,
        exclude_scientific=True,
    )
    if len(synonym_rows) == 1:
        return _finalize_unique_result(
            request,
            synonym_rows[0],
            db_path=db_path,
            status=ResolutionStatus.RESOLVED_EXACT_SYNONYM,
            match_type=MatchType.EXACT_SYNONYM,
            warnings=[WarningCode.SYNONYM_MATCHED],
        )
    if len(synonym_rows) > 1:
        return _ambiguous_result(
            request,
            synonym_rows,
            db_path=db_path,
            match_type=MatchType.EXACT_SYNONYM,
            warning=WarningCode.MULTIPLE_EXACT_CANDIDATES,
        )

    normalized_rows = _coalesce_normalized_matches(
        fetch_name_matches(
            db_path,
            normalized_name=normalize_name(request.original_name),
        )
    )
    if len(normalized_rows) == 1:
        return _finalize_unique_result(
            request,
            normalized_rows[0],
            db_path=db_path,
            status=ResolutionStatus.RESOLVED_NORMALIZED,
            match_type=MatchType.NORMALIZED,
            warnings=[WarningCode.NORMALIZED_MATCHED],
        )
    if len(normalized_rows) > 1:
        return _ambiguous_result(
            request,
            normalized_rows,
            db_path=db_path,
            match_type=MatchType.NORMALIZED,
            warning=WarningCode.MULTIPLE_EXACT_CANDIDATES,
        )

    return None
