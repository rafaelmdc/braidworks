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
class StepOutcome:
    """What one braid step did for one entity — the completion-metadata record.

    Independent braid branches can each succeed or come up empty for the same entity
    (e.g. an organism has disease associations but no curated traits). A NO_MATCH on
    one branch is not an entity-level failure; it is recorded here so callers can see
    exactly which branches produced data. ``status`` is one of:

    - ``"ok"`` — the step produced output (or its outputs were already present);
    - ``"no_match"`` — the step ran but found nothing for this entity;
    - ``"skipped"`` — the step never ran because an upstream branch did not produce
      its required input type.
    """

    capability_id: str
    backend: str
    status: str
    produced: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "backend": self.backend,
            "status": self.status,
            "produced": list(self.produced),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> StepOutcome:
        return cls(
            capability_id=data["capability_id"],
            backend=data.get("backend", ""),
            status=data["status"],
            produced=tuple(data.get("produced", ())),
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
    # Per-step completion metadata (one entry per braid step that touched this
    # entity). Populated by the executor; empty for a freshly built input set.
    completion: list[StepOutcome] = field(default_factory=list)
    # Fan-out lineage: when a one→many step forks an entity into children
    # (cardinality fan-out), each child records the entity_id of the *originating
    # input* it descended from, so callers can regroup leaves by the original query.
    # ``None`` for a plain input set that was never forked.
    parent_id: str | None = None

    @classmethod
    def from_strands(cls, entity_id: str, strands: list[Strand]) -> StrandSet:
        return cls(entity_id=entity_id, _strands={s.type_id: s for s in strands})

    def clone(self, *, entity_id: str | None = None, parent_id: str | None = None) -> StrandSet:
        """A detached copy for fan-out forking. Strands are immutable by convention,
        so the strand objects are shared; the mutable containers are copied so each
        child accumulates its own completion / warnings / errors independently."""
        return StrandSet(
            entity_id=entity_id if entity_id is not None else self.entity_id,
            _strands=dict(self._strands),
            requires_review=self.requires_review,
            warnings=list(self.warnings),
            errors=list(self.errors),
            completion=list(self.completion),
            parent_id=parent_id if parent_id is not None else self.parent_id,
        )

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
            "completion": [o.to_json() for o in self.completion],
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> StrandSet:
        return cls(
            entity_id=data["entity_id"],
            _strands={tid: Strand.from_json(s) for tid, s in data.get("strands", {}).items()},
            requires_review=data.get("requires_review", False),
            warnings=list(data.get("warnings", [])),
            errors=list(data.get("errors", [])),
            completion=[StepOutcome.from_json(o) for o in data.get("completion", [])],
            parent_id=data.get("parent_id"),
        )
