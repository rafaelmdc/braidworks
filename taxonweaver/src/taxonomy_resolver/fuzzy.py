"""Supervised fuzzy suggestion layer placeholder.

Phase 6 adds candidate generation and scoring without altering the
deterministic-first resolution order.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .db import fetch_fuzzy_name_pool
from .lineage import get_lineage_for_taxid, lineage_entries_from_json
from .normalize import normalize_level, normalize_name
from .policy import MatchType
from .schemas import CandidateMatch, ResolveRequest

DatabaseHandle = sqlite3.Connection | str | Path

try:
    from rapidfuzz import fuzz

    RAPIDFUZZ_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in constrained environments
    from difflib import SequenceMatcher

    RAPIDFUZZ_AVAILABLE = False

    def _ratio(left: str, right: str) -> float:
        """Compatibility scorer when RapidFuzz is unavailable locally."""

        return SequenceMatcher(None, left, right).ratio() * 100

    def _token_set_ratio(left: str, right: str) -> float:
        """Approximate token-set score without requiring the external dependency."""

        left_tokens = " ".join(sorted(set(left.split())))
        right_tokens = " ".join(sorted(set(right.split())))
        return SequenceMatcher(None, left_tokens, right_tokens).ratio() * 100

    def _partial_ratio(left: str, right: str) -> float:
        """Approximate partial score by comparing shorter/longer strings directly."""

        shorter, longer = sorted((left, right), key=len)
        return SequenceMatcher(None, shorter, longer).ratio() * 100
else:
    _ratio = fuzz.ratio
    _token_set_ratio = fuzz.token_set_ratio
    _partial_ratio = fuzz.partial_ratio


def _similarity_score(
    normalized_input: str,
    candidate_normalized: str,
    *,
    provided_level: str | None,
    candidate_rank: str,
    scientific_name_match: bool,
) -> float:
    """Score a fuzzy candidate using conservative string and rank signals.

    RapidFuzz is preferred because it is substantially faster and provides
    better token-aware metrics for large candidate pools. A small local fallback
    remains so the package still imports in constrained environments.
    """

    direct_ratio = _ratio(normalized_input, candidate_normalized)
    token_ratio = _token_set_ratio(normalized_input, candidate_normalized)
    partial_ratio = _partial_ratio(normalized_input, candidate_normalized)
    score = direct_ratio * 0.50 + token_ratio * 0.35 + partial_ratio * 0.15
    input_token_count = len(normalized_input.split())
    candidate_token_count = len(candidate_normalized.split())
    score -= abs(input_token_count - candidate_token_count) * 6.0

    if scientific_name_match:
        score += 2.0
    if provided_level is not None and normalize_level(candidate_rank) == provided_level:
        score += 3.0

    return min(score, 100.0)


def suggest_fuzzy_candidates(
    request: ResolveRequest,
    db_path: DatabaseHandle,
    *,
    max_candidates: int = 5,
) -> list[CandidateMatch]:
    """Return review-only fuzzy candidates after deterministic lookup fails."""

    normalized_input = normalize_name(request.original_name)
    provided_level = normalize_level(request.provided_level)
    rows = fetch_fuzzy_name_pool(db_path, normalized_input)
    if not rows:
        return []

    best_by_taxid: dict[int, tuple[float, object]] = {}
    for row in rows:
        taxid = int(row["taxid"])
        score = _similarity_score(
            normalized_input,
            str(row["normalized_name"]),
            provided_level=provided_level,
            candidate_rank=str(row["rank"]),
            scientific_name_match=str(row["name_class"]) == "scientific name",
        )
        existing = best_by_taxid.get(taxid)
        if existing is None or score > existing[0]:
            best_by_taxid[taxid] = (score, row)

    ranked = sorted(
        best_by_taxid.values(),
        key=lambda item: (item[0], str(item[1]["name_class"]) == "scientific name"),
        reverse=True,
    )
    if not ranked:
        return []

    # Drop very weak suggestions so unresolved stays unresolved.
    ranked = [item for item in ranked if item[0] >= 72.0]
    if not ranked:
        return []

    top_score = ranked[0][0]
    if top_score < 80.0:
        return []

    if len(ranked) == 1 or (top_score >= 90.0 and top_score - ranked[1][0] >= 5.0):
        ranked = ranked[:1]
    else:
        ranked = ranked[:max_candidates]

    return [
        CandidateMatch(
            taxid=int(row["taxid"]),
            name=str(row["scientific_name"] or row["matched_name"]),
            rank=str(row["rank"]),
            match_type=MatchType.FUZZY,
            score=round(score, 2),
            lineage=(
                lineage_entries_from_json(row["lineage_json"])
                or get_lineage_for_taxid(db_path, int(row["taxid"]))
            ),
        )
        for score, row in ranked
    ]
