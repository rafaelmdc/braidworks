"""Neutral resolution intermediate shared by both taxon backends.

Both ``LocalTaxonomyBackend`` and ``DatasetsV2Backend`` normalize their native
responses into a ``TaxonMatch`` before the single ``mapper`` turns it into a
``WeaveResult``. This is what guarantees the two backends emit identical strand
shapes even when their matching differs. These types are taxon-specific and must
never leak into ``braidworks-core``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TaxonMatchStatus(Enum):
    """Backend-neutral outcome for one resolved name."""

    RESOLVED = "resolved"  # a confident single match
    FUZZY_UNIQUE = "fuzzy_unique"  # one suggested match, needs review
    AMBIGUOUS = "ambiguous"  # multiple candidates
    NO_MATCH = "no_match"  # nothing found
    ERROR = "error"  # per-entity backend failure


@dataclass
class LineageEntry:
    """One ancestor in a taxon's lineage (root-first; last entry is the taxon)."""

    taxid: int
    rank: str
    name: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LineageEntry:
        return cls(**data)


@dataclass
class CandidateMatch:
    """One alternative when a match is ambiguous or fuzzy."""

    taxid: int
    name: str
    rank: str
    match_type: str = "none"
    score: float | None = None  # 0..100 scale, like ResolveResult.score
    lineage: list[LineageEntry] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CandidateMatch:
        fields = dict(data)
        fields["lineage"] = [LineageEntry.from_json(row) for row in data.get("lineage", [])]
        return cls(**fields)


@dataclass
class TaxonMatch:
    """One backend's resolution of one input name. Backend-neutral."""

    query: str
    status: TaxonMatchStatus
    taxid: int | None = None
    scientific_name: str | None = None
    rank: str | None = None
    parent_taxid: int | None = None
    match_type: str = "none"
    score: float | None = None  # 0..100 scale; None means "treat as exact (1.0)"
    requires_review: bool = False
    candidates: list[CandidateMatch] = field(default_factory=list)
    lineage: list[LineageEntry] = field(default_factory=list)
    # Ancestor taxids before name/rank resolution (API backend scratch space; the
    # local backend leaves this empty and fills ``lineage`` directly).
    lineage_taxids: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> TaxonMatch:
        fields = dict(data)
        fields["status"] = TaxonMatchStatus(data["status"])
        fields["lineage"] = [LineageEntry.from_json(row) for row in data.get("lineage", [])]
        fields["candidates"] = [CandidateMatch.from_json(row) for row in data.get("candidates", [])]
        fields["lineage_taxids"] = list(data.get("lineage_taxids", []))
        fields["warnings"] = list(data.get("warnings", []))
        return cls(**fields)
