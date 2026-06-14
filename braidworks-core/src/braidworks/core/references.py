"""Automatic references: turn the sources a braid touched into citations.

The runtime half of issue #1. Every weaver carries
:class:`~braidworks.core.capability.Provenance`; given the weavers a braid used (its
steps name them) and the registry that holds their manifests, this builds a deduped,
deterministically-ordered bibliography whose form is driven by each source's license
(see :mod:`braidworks.core.licenses`). Attach it to a result, print it from the CLI, or
render it in the visualizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

from braidworks.core.licenses import (
    ATTRIBUTION_REQUIRED,
    CITE_REQUESTED,
    citation_requirement,
)

if TYPE_CHECKING:
    from braidworks.core.braid import Braid
    from braidworks.core.registry import BraidRegistry


@dataclass(frozen=True)
class Reference:
    """One source to credit, with its license-driven citation requirement."""

    weaver_id: str
    source_url: str
    license: str
    citation: str
    attribution: str
    requirement: str  # citation_requirement(license): cite_requested / ... / restricted

    def render(self) -> str:
        """A one-line human citation, phrased per the license requirement."""
        who = self.attribution or self.weaver_id
        src = f" — {self.source_url}" if self.source_url else ""
        if self.requirement == ATTRIBUTION_REQUIRED:
            note = "attribution required"
        elif self.requirement == CITE_REQUESTED:
            note = "citation requested"
        else:
            note = "reuse terms unverified, confirm before redistribution"
        lic = self.license or "unspecified"
        cite = f" Cite: {self.citation}." if self.citation else ""
        return f"{who}{src} (licensed {lic}; {note}).{cite}"

    def to_json(self) -> dict[str, Any]:
        return {
            "weaver_id": self.weaver_id,
            "source_url": self.source_url,
            "license": self.license,
            "citation": self.citation,
            "attribution": self.attribution,
            "requirement": self.requirement,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Reference:
        return cls(
            weaver_id=data["weaver_id"],
            source_url=data.get("source_url", ""),
            license=data.get("license", ""),
            citation=data.get("citation", ""),
            attribution=data.get("attribution", ""),
            requirement=data.get("requirement", ""),
        )


def references_for(
    weaver_ids: Iterable[str], registry: BraidRegistry
) -> tuple[Reference, ...]:
    """References for the given weavers, deduped and ordered by weaver_id.

    Weavers with no provenance (or empty provenance) contribute nothing — a missing
    citation is silently omitted rather than rendered as a blank entry.
    """
    refs: dict[str, Reference] = {}
    for wid in set(weaver_ids):
        manifest = registry.get_manifest(wid)
        if manifest is None or manifest.provenance is None or manifest.provenance.is_empty():
            continue
        p = manifest.provenance
        refs[wid] = Reference(
            weaver_id=wid,
            source_url=p.source_url,
            license=p.license,
            citation=p.citation,
            attribution=p.attribution,
            requirement=citation_requirement(p.license),
        )
    return tuple(refs[wid] for wid in sorted(refs))


def references_for_braid(braid: Braid, registry: BraidRegistry) -> tuple[Reference, ...]:
    """References for every weaver a braid's steps invoke."""
    return references_for((step.weaver_id for step in braid.steps), registry)


def format_references(refs: Iterable[Reference]) -> str:
    """Render references as a plain-text bullet bibliography ('' if none)."""
    lines = [f"- {r.render()}" for r in refs]
    return "\n".join(lines)
