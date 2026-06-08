"""Neutral backend records — the shape every backend normalizes its source into.

Domain-neutral by construction: a record carries values keyed by ``type_id``
(matching the spec's produced types), never typed domain fields, so this stays in
core without leaking taxonomy/protein/etc. assumptions. The single shared mapper
(:mod:`braidworks.core.mapper`) turns these into :class:`WeaveResult`s, which is
what guarantees every backend of a weaver emits identical strand shapes.

Two shapes, picked by the weaver's ``kind``:

- :class:`LookupRecord` — clean id→data (found / values / error).
- :class:`ResolverRecord` — fuzzy/ambiguous matching (a :class:`MatchStatus`,
  optional ``score`` / ``requires_review``, and ranked :class:`Candidate`s).

A weaver that needs richer, *typed* internals may define its own record and map it
itself (see decisions.md "thin contract, free implementation"); these are the
shared default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MatchStatus(Enum):
    """Backend-neutral outcome for one resolved input (resolver weavers)."""

    RESOLVED = "resolved"  # a confident single match
    FUZZY_UNIQUE = "fuzzy_unique"  # one low-confidence guess; needs review
    AMBIGUOUS = "ambiguous"  # multiple candidates, no single answer
    NO_MATCH = "no_match"  # nothing found
    ERROR = "error"  # per-entity backend failure


@dataclass
class Candidate:
    """One alternative when a match is ambiguous (values keyed by produced type_id)."""

    values: dict[str, Any] = field(default_factory=dict)
    score: float | None = None  # 0..1 fraction, or a 0..100 fuzzy score


@dataclass
class LookupRecord:
    """One backend's lookup of one input. Fill ``values`` with produced type_ids."""

    query: dict[str, Any]
    found: bool = False
    values: dict[str, Any] = field(default_factory=dict)
    error: str | None = None  # per-entity failure; a miss is found=False, not an error


@dataclass
class ResolverRecord:
    """One backend's resolution of one input (fuzzy/ambiguous). Backend-neutral."""

    query: dict[str, Any]
    status: MatchStatus = MatchStatus.NO_MATCH
    values: dict[str, Any] = field(default_factory=dict)
    score: float | None = None  # None means "treat as exact (1.0)"
    requires_review: bool = False
    candidates: list[Candidate] = field(default_factory=list)
    error: str | None = None
