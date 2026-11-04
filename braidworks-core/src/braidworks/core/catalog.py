"""Find fields by meaning: a searchable catalogue of the installed sources' types.

Each installed weaver describes the types it consumes and produces
(``WeaverManifest.type_descriptions``). :func:`field_catalog` gathers them with who
provides each type and what it is produced from; :func:`rank_fields` scores the
catalogue against a few plain words ("pdb structures", "pathways").

Domain-neutral: ranking uses only type ids, descriptions and how many capabilities
use a type. Matching is by whole word or word start, so "go" finds
``go.biological_process`` but not ``eggnog.group``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from braidworks.core.registry import BraidRegistry

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({"a", "an", "and", "by", "for", "from", "in", "of", "on", "the", "to"})


def _stem(word: str) -> str:
    """Fold simple plurals so "structures" matches "structure"."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def _words(text: str) -> list[str]:
    return [_stem(w) for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


@dataclass(frozen=True)
class FieldInfo:
    """One type in the catalogue."""

    type_id: str
    description: str
    sources: tuple[str, ...]  # weaver ids that consume or produce it
    inputs: tuple[str, ...]  # what producing capabilities start from
    consumers: int  # capabilities that accept it as input (0: output only)

    def to_json(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "description": self.description,
            "sources": list(self.sources),
            "inputs": list(self.inputs),
            "consumers": self.consumers,
        }


def field_catalog(registry: BraidRegistry) -> dict[str, FieldInfo]:
    """Every type the installed sources consume or produce, with its description."""
    descriptions: dict[str, str] = {}
    sources: dict[str, set[str]] = {}
    inputs: dict[str, set[str]] = {}
    consumers: dict[str, int] = {}
    for manifest in registry.declared_manifests():
        for type_id, text in manifest.type_descriptions.items():
            descriptions.setdefault(type_id, text)
        for cap in manifest.capabilities:
            for type_id in cap.consumes:
                sources.setdefault(type_id, set()).add(manifest.weaver_id)
                consumers[type_id] = consumers.get(type_id, 0) + 1
            for type_id in cap.produces:
                sources.setdefault(type_id, set()).add(manifest.weaver_id)
                inputs.setdefault(type_id, set()).update(cap.consumes)
    return {
        type_id: FieldInfo(
            type_id=type_id,
            description=descriptions.get(type_id, ""),
            sources=tuple(sorted(found)),
            inputs=tuple(sorted(inputs.get(type_id, ()))),
            consumers=consumers.get(type_id, 0),
        )
        for type_id, found in sorted(sources.items())
    }


@dataclass(frozen=True)
class FieldMatch:
    """A catalogue entry and how well it matched the search."""

    info: FieldInfo
    score: float

    @property
    def type_id(self) -> str:
        return self.info.type_id

    @property
    def description(self) -> str:
        return self.info.description

    def to_json(self) -> dict[str, Any]:
        return {**self.info.to_json(), "score": round(self.score, 3)}


def _score(query: list[str], info: FieldInfo) -> float:
    name = set(_words(info.type_id.replace("_", " ")))
    described = set(_words(info.description))
    total = 0.0
    matched = 0
    for word in query:
        points = 0.0
        if word in name:
            points += 3
        elif len(word) >= 3 and any(n.startswith(word) for n in name):
            points += 1.5
        if word in described:
            points += 1
        elif len(word) >= 3 and any(d.startswith(word) for d in described):
            points += 0.5
        if points:
            matched += 1
            total += points
    if not matched:
        return 0.0
    # Fields matching only some of the words rank below fields matching all of them.
    score = total * matched / len(query)
    # Up to +1 when the words cover more of the name ("organism name" -> organism.name
    # over organism.scientific_name), and up to +1 for widely used join keys
    # ("taxon" -> ncbi.taxon.id over ncbi.taxon.parent_id).
    score += len(name & set(query)) / len(name) if name else 0.0
    score += 0.25 * min(info.consumers, 4)
    return score


def rank_fields(text: str, catalog: dict[str, FieldInfo], limit: int = 10) -> list[FieldMatch]:
    """Fields matching ``text``, best first; ties prefer more widely used fields."""
    query = _words(text)
    if not query:
        return []
    exact = text.strip().lower()
    matches = []
    for info in catalog.values():
        score = _score(query, info) + (100 if info.type_id.lower() == exact else 0)
        if score > 0:
            matches.append(FieldMatch(info, score))
    matches.sort(key=lambda m: (-m.score, -m.info.consumers, len(m.type_id), m.type_id))
    return matches[:limit]


class FieldMatches(list):
    """``find`` results: a list of :class:`FieldMatch` that prints as a readable table."""

    def to_json(self) -> list[dict[str, Any]]:
        return [match.to_json() for match in self]

    def _lines(self) -> list[tuple[str, str, str]]:
        rows = []
        for match in self:
            info = match.info
            origin = f"from {', '.join(info.inputs)}" if info.inputs else "an input you supply"
            rows.append(
                (
                    info.type_id,
                    info.description or "(no description)",
                    f"{', '.join(info.sources)}; {origin}",
                )
            )
        return rows

    def __repr__(self) -> str:
        if not self:
            return "<no matching fields — try other words, or run `braidworks keys`>"
        width = max(len(type_id) for type_id, _, _ in self._lines())
        return "\n".join(
            f"{type_id:<{width}}  {description}\n{'':<{width}}  ({where})"
            for type_id, description, where in self._lines()
        )

    def _repr_html_(self) -> str:
        cells = "".join(
            f"<tr><td><code>{html.escape(t)}</code></td><td>{html.escape(d)}</td>"
            f"<td>{html.escape(w)}</td></tr>"
            for t, d, w in self._lines()
        )
        return (
            "<table><thead><tr><th>field</th><th>meaning</th><th>source</th></tr></thead>"
            f"<tbody>{cells}</tbody></table>"
        )
