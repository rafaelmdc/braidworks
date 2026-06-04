"""Shared status and warning definitions for resolver workflows.

Keeping workflow vocabulary in one place prevents CLI, services, and later
Django integration from drifting into incompatible string literals.
"""

from __future__ import annotations

from enum import StrEnum

from .normalize import normalize_level


class ResolutionStatus(StrEnum):
    """High-level machine and review statuses used across the project."""

    RESOLVED_EXACT_SCIENTIFIC = "resolved_exact_scientific"
    RESOLVED_EXACT_SYNONYM = "resolved_exact_synonym"
    RESOLVED_NORMALIZED = "resolved_normalized"
    SUGGESTED_FUZZY_UNIQUE = "suggested_fuzzy_unique"
    AMBIGUOUS_FUZZY_MULTIPLE = "ambiguous_fuzzy_multiple"
    UNRESOLVED_VAGUE_LABEL = "unresolved_vague_label"
    UNRESOLVED_NO_MATCH = "unresolved_no_match"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    CONFIRMED_BY_USER = "confirmed_by_user"
    REJECTED_BY_USER = "rejected_by_user"
    LEVEL_CONFLICT = "level_conflict"


class MatchType(StrEnum):
    """How a candidate or resolved taxon was reached."""

    EXACT_SCIENTIFIC = "exact_scientific"
    EXACT_SYNONYM = "exact_synonym"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"
    CACHED = "cached"
    USER_CONFIRMED = "user_confirmed"
    USER_SELECTED = "user_selected"
    NONE = "none"


class WarningCode(StrEnum):
    """Non-terminal annotations that downstream consumers should surface."""

    PROVIDED_LEVEL_CONFLICT = "provided_level_conflict"
    MULTIPLE_EXACT_CANDIDATES = "multiple_exact_candidates"
    MULTIPLE_FUZZY_CANDIDATES = "multiple_fuzzy_candidates"
    SYNONYM_MATCHED = "synonym_matched"
    NORMALIZED_MATCHED = "normalized_matched"
    TRANSFORM_APPLIED = "transform_applied"
    VAGUE_LABEL_DETECTED = "vague_label_detected"
    PLACEHOLDER_LABEL_DETECTED = "placeholder_label_detected"
    CACHED_DECISION_REUSED = "cached_decision_reused"
    NOT_IMPLEMENTED = "not_implemented"


REVIEW_REQUIRED_STATUSES = {
    ResolutionStatus.SUGGESTED_FUZZY_UNIQUE,
    ResolutionStatus.AMBIGUOUS_FUZZY_MULTIPLE,
    ResolutionStatus.UNRESOLVED_VAGUE_LABEL,
    ResolutionStatus.UNRESOLVED_NO_MATCH,
    ResolutionStatus.MANUAL_REVIEW_REQUIRED,
    ResolutionStatus.LEVEL_CONFLICT,
}

AUTO_ACCEPT_STATUSES = {
    ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC,
    ResolutionStatus.RESOLVED_EXACT_SYNONYM,
    ResolutionStatus.RESOLVED_NORMALIZED,
    ResolutionStatus.CONFIRMED_BY_USER,
}


def requires_review(status: ResolutionStatus) -> bool:
    """Return whether a result status should enter a review queue."""

    return status in REVIEW_REQUIRED_STATUSES


def allows_auto_accept(status: ResolutionStatus) -> bool:
    """Return whether a result status is safe to auto-accept by policy."""

    return status in AUTO_ACCEPT_STATUSES


def apply_level_conflict_policy(
    status: ResolutionStatus,
    warnings: list[WarningCode],
    *,
    provided_level: str | None,
    matched_rank: str | None,
) -> tuple[ResolutionStatus, list[WarningCode]]:
    """Promote deterministic hits to level conflict when rank mismatches exist."""

    normalized_provided_level = normalize_level(provided_level)
    normalized_matched_rank = normalize_level(matched_rank)
    result_warnings = list(warnings)

    if (
        normalized_provided_level is not None
        and normalized_matched_rank is not None
        and normalized_provided_level != normalized_matched_rank
        and WarningCode.PROVIDED_LEVEL_CONFLICT not in result_warnings
    ):
        result_warnings.append(WarningCode.PROVIDED_LEVEL_CONFLICT)
        return ResolutionStatus.LEVEL_CONFLICT, result_warnings

    return status, result_warnings


def classify_fuzzy_status(candidate_count: int) -> tuple[ResolutionStatus, list[WarningCode]]:
    """Map the fuzzy candidate count to a stable status and warnings list."""

    if candidate_count <= 0:
        return ResolutionStatus.UNRESOLVED_NO_MATCH, []
    if candidate_count == 1:
        return ResolutionStatus.SUGGESTED_FUZZY_UNIQUE, []
    return ResolutionStatus.AMBIGUOUS_FUZZY_MULTIPLE, [WarningCode.MULTIPLE_FUZZY_CANDIDATES]
