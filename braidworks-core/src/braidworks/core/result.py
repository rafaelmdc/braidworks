"""WeaveResult, WeaveStatus, CandidateResult — what one capability call returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from braidworks.core.strand import Strand


class WeaveStatus(Enum):
    """Outcome of one capability invocation for one input StrandSet."""

    OK = "ok"  # resolved; strands populated
    NO_MATCH = "no_match"  # nothing found; strands empty (a valid data outcome)
    AMBIGUOUS = "ambiguous"  # multiple candidates; strands empty, candidates populated
    ERROR = "error"  # per-entity weaver failure; strands empty, errors populated


@dataclass
class CandidateResult:
    """One alternative when a result is ambiguous."""

    strands: tuple[Strand, ...] = ()
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "strands": [s.to_json() for s in self.strands],
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CandidateResult:
        return cls(
            strands=tuple(Strand.from_json(s) for s in data.get("strands", [])),
            confidence=data.get("confidence", 0.0),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class WeaveResult:
    """Exactly one per input StrandSet. Failures are values, not exceptions.

    ``computed_groups`` must reflect every group actually computed, including
    groups computed internally as dependencies — the cache relies on it.
    """

    capability_id: str
    capability_version: str
    backend_used: str  # actual backend: "local" or "api", never "any"
    computed_groups: frozenset[str]
    status: WeaveStatus
    strands: tuple[Strand, ...] = ()
    candidates: tuple[CandidateResult, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    requires_review: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "backend_used": self.backend_used,
            "computed_groups": sorted(self.computed_groups),
            "status": self.status.value,
            "strands": [s.to_json() for s in self.strands],
            "candidates": [c.to_json() for c in self.candidates],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "requires_review": self.requires_review,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> WeaveResult:
        return cls(
            capability_id=data["capability_id"],
            capability_version=data["capability_version"],
            backend_used=data["backend_used"],
            computed_groups=frozenset(data.get("computed_groups", [])),
            status=WeaveStatus(data["status"]),
            strands=tuple(Strand.from_json(s) for s in data.get("strands", [])),
            candidates=tuple(CandidateResult.from_json(c) for c in data.get("candidates", [])),
            warnings=tuple(data.get("warnings", [])),
            errors=tuple(data.get("errors", [])),
            requires_review=data.get("requires_review", False),
        )
