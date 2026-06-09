"""Strand, StrandSet, and MergePolicy — the atomic data units of Braidworks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from braidworks.core.keytypes import canonicalize

if TYPE_CHECKING:
    from braidworks.core.result import WeaveResult

JSONValue = str | int | float | list | dict | None


class MergePolicy(Enum):
    """How to resolve a collision when a type_id already exists in a StrandSet."""

    HIGHEST_CONFIDENCE = "highest_confidence"  # keep whichever scores higher (default)
    FIRST_WINS = "first_wins"  # never overwrite
    LAST_WINS = "last_wins"  # always overwrite


@dataclass
class Strand:
    """The atomic unit of data. Immutable by convention (see architecture).

    Callers creating input strands need only ``type_id`` and ``value``. Weavers
    populate ``confidence`` and ``provenance`` on produced strands. ``confidence``
    is a quality score in [0.0, 1.0], not a calibrated probability.
    """

    type_id: str
    value: JSONValue
    confidence: float = 1.0
    provenance: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalize the value to the canonical type for this (shared) key, so the
        # same identifier has one shape everywhere — consistent cache keys + joins.
        # Unregistered (weaver-private) keys pass through unchanged.
        self.value = canonicalize(self.type_id, self.value)

    def to_json(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "value": self.value,
            "confidence": self.confidence,
            "provenance": list(self.provenance),
            "metadata": self.metadata,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Strand:
        return cls(
            type_id=data["type_id"],
            value=data["value"],
            confidence=data.get("confidence", 1.0),
            provenance=tuple(data.get("provenance", ())),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class StrandSet:
    """All strands currently known for one entity. Mutable during execution.

    The internal ``_strands`` mapping is not public API: construct with
    ``from_strands`` and read with ``get``/``has``. One strand per type_id;
    collection types store their list as the strand's ``value``.
    """

    entity_id: str
    _strands: dict[str, Strand] = field(default_factory=dict)
    requires_review: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_strands(cls, entity_id: str, strands: list[Strand]) -> StrandSet:
        return cls(entity_id=entity_id, _strands={s.type_id: s for s in strands})

    def has(self, type_id: str) -> bool:
        return type_id in self._strands

    def get(self, type_id: str) -> Strand | None:
        return self._strands.get(type_id)

    def available_types(self) -> frozenset[str]:
        return frozenset(self._strands)

    def add_strand(
        self, strand: Strand, policy: MergePolicy = MergePolicy.HIGHEST_CONFIDENCE
    ) -> None:
        """Insert a single strand, resolving any collision per ``policy``."""
        existing = self._strands.get(strand.type_id)
        if existing is None:
            self._strands[strand.type_id] = strand
            return
        if policy is MergePolicy.FIRST_WINS:
            return
        if policy is MergePolicy.LAST_WINS:
            self._strands[strand.type_id] = strand
            return
        # HIGHEST_CONFIDENCE: replace only on a strict improvement (ties keep existing).
        if strand.confidence > existing.confidence:
            self._strands[strand.type_id] = strand

    def merge_result(
        self, result: WeaveResult, policy: MergePolicy = MergePolicy.HIGHEST_CONFIDENCE
    ) -> None:
        """Fold a ``WeaveResult``'s strands and flags into this set per ``policy``."""
        for strand in result.strands:
            self.add_strand(strand, policy)
        if result.requires_review:
            self.requires_review = True
        self.warnings.extend(result.warnings)
        self.errors.extend(result.errors)

    def to_json(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "strands": {tid: s.to_json() for tid, s in self._strands.items()},
            "requires_review": self.requires_review,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> StrandSet:
        return cls(
            entity_id=data["entity_id"],
            _strands={tid: Strand.from_json(s) for tid, s in data.get("strands", {}).items()},
            requires_review=data.get("requires_review", False),
            warnings=list(data.get("warnings", [])),
            errors=list(data.get("errors", [])),
        )
