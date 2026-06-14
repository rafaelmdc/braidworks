"""Serializable request/response models for the resolver.

Dataclasses keep the internal contract explicit and easy to convert to JSON
without adding a heavy dependency before it is justified.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from .policy import MatchType, ResolutionStatus, WarningCode


def _serialize_json_ready(value: Any) -> Any:
    """Recursively convert dataclasses and enums into JSON-safe values."""

    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {key: _serialize_json_ready(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _serialize_json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_json_ready(item) for item in value]
    return value


class DecisionAction(StrEnum):
    """User actions recorded against a resolver result."""

    CONFIRM = "confirm"
    REJECT = "reject"
    CHOOSE_CANDIDATE = "choose_candidate"
    MANUAL_REVIEW = "manual_review"
    SKIP = "skip"


@dataclass(slots=True)
class LineageEntry:
    """One lineage level in rank order."""

    taxid: int
    rank: str
    name: str


@dataclass(slots=True)
class CandidateMatch:
    """A potential taxon candidate surfaced by the resolver."""

    taxid: int
    name: str
    rank: str
    match_type: MatchType
    score: float | None = None
    lineage: list[LineageEntry] = field(default_factory=list)
    warnings: list[WarningCode] = field(default_factory=list)


@dataclass(slots=True)
class ResolveRequest:
    """Stable input contract for resolving a single organism name."""

    original_name: str
    provided_level: str | None = None
    allow_fuzzy: bool = True
    source: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResolveResult:
    """Stable output contract for single-name resolution."""

    original_name: str
    normalized_name: str
    provided_level: str | None
    status: ResolutionStatus
    review_required: bool
    auto_accept: bool
    match_type: MatchType
    warnings: list[WarningCode] = field(default_factory=list)
    matched_taxid: int | None = None
    matched_name: str | None = None
    matched_rank: str | None = None
    score: float | None = None
    candidates: list[CandidateMatch] = field(default_factory=list)
    lineage: list[LineageEntry] = field(default_factory=list)
    cache_applied: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation for CLI and future API use."""

        return _serialize_json_ready(self)


@dataclass(slots=True)
class BatchResolveRequest:
    """Container for batch resolution runs."""

    items: list[ResolveRequest]
    batch_id: str | None = None


@dataclass(slots=True)
class BatchResolveResult:
    """Batch response plus a lightweight status summary."""

    results: list[ResolveResult]
    batch_id: str | None = None
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation for file interchange."""

        return _serialize_json_ready(self)


@dataclass(slots=True)
class DecisionRecord:
    """Persisted user action used by the reviewed mapping cache."""

    action: DecisionAction
    original_name: str
    normalized_name: str
    provided_level: str | None
    taxonomy_build_version: str
    reviewer: str | None = None
    resolved_taxid: int | None = None
    matched_scientific_name: str | None = None
    match_type: MatchType = MatchType.NONE
    status: ResolutionStatus = ResolutionStatus.MANUAL_REVIEW_REQUIRED
    score: float | None = None
    warnings: list[WarningCode] = field(default_factory=list)
    notes: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation for cache persistence."""

        return _serialize_json_ready(self)
