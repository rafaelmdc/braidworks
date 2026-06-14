"""OutputGroup, Capability, WeaverManifest — the declarative capability model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OutputGroup:
    """A set of outputs computed together from one underlying operation.

    Requesting any output in a group triggers the whole group; requesting
    nothing from a group skips it entirely. Internal execution ordering and
    dependencies are the weaver's concern — there is deliberately no
    ``depends_on`` or ``marginal_cost`` here.
    """

    id: str
    outputs: frozenset[str]

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "outputs": sorted(self.outputs)}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> OutputGroup:
        return cls(id=data["id"], outputs=frozenset(data["outputs"]))


@dataclass(frozen=True)
class Capability:
    """One declared operation: consumes input types, produces output types."""

    id: str
    consumes: frozenset[str]
    produces: frozenset[str]
    output_groups: tuple[OutputGroup, ...]
    backends: tuple[str, ...]
    max_batch_size: int | None = None
    cost: float = 1.0
    # Group ids the backend always computes internally, even when none of their
    # outputs were requested (e.g. a resolver always resolves name->id "core"
    # before fetching lineage). Unioned into WeaveResult.computed_groups so the
    # cache key isn't under-reported. Does not, by itself, emit those outputs.
    always_computed_groups: frozenset[str] = frozenset()

    def triggered_groups(self, requested: frozenset[str]) -> frozenset[str]:
        """Group ids containing at least one of the requested outputs."""
        return frozenset(
            g.id for g in self.output_groups if g.outputs & requested
        )

    def outputs_to_compute(self, requested: frozenset[str]) -> frozenset[str]:
        """Union of every triggered group's outputs, intersected with ``produces``.

        A weaver must produce exactly these externally; it may compute more
        internally and report them via ``WeaveResult.computed_groups``.
        """
        triggered = self.triggered_groups(requested)
        out: set[str] = set()
        for g in self.output_groups:
            if g.id in triggered:
                out |= g.outputs
        return frozenset(out & self.produces)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "consumes": sorted(self.consumes),
            "produces": sorted(self.produces),
            "output_groups": [g.to_json() for g in self.output_groups],
            "backends": list(self.backends),
            "max_batch_size": self.max_batch_size,
            "cost": self.cost,
            "always_computed_groups": sorted(self.always_computed_groups),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Capability:
        return cls(
            id=data["id"],
            consumes=frozenset(data["consumes"]),
            produces=frozenset(data["produces"]),
            output_groups=tuple(OutputGroup.from_json(g) for g in data["output_groups"]),
            backends=tuple(data["backends"]),
            max_batch_size=data.get("max_batch_size"),
            cost=data.get("cost", 1.0),
            always_computed_groups=frozenset(data.get("always_computed_groups", ())),
        )


@dataclass(frozen=True)
class Provenance:
    """Where a weaver's data comes from and how it must be credited.

    Mirrors the structured ``[weaver]`` source/license fields in ``weaver.spec.toml``
    so a *running* braid can introspect which source each weaver drew on and emit the
    references that source requires. ``license`` is a short identifier (ideally SPDX,
    e.g. ``CC-BY-4.0`` / ``CC0-1.0``); ``citation`` is the DOI or reference text;
    ``attribution`` names the provider to credit (e.g. ``UniProt Consortium``). All
    fields are optional so a manifest without provenance is still valid.
    """

    source_url: str = ""
    license: str = ""
    citation: str = ""
    attribution: str = ""

    def is_empty(self) -> bool:
        return not (self.source_url or self.license or self.citation or self.attribution)

    def to_json(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "license": self.license,
            "citation": self.citation,
            "attribution": self.attribution,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Provenance:
        return cls(
            source_url=data.get("source_url", ""),
            license=data.get("license", ""),
            citation=data.get("citation", ""),
            attribution=data.get("attribution", ""),
        )


@dataclass(frozen=True)
class WeaverManifest:
    """Static declaration of a weaver's capabilities. Read before instantiation."""

    weaver_id: str
    version: str
    capabilities: tuple[Capability, ...] = field(default_factory=tuple)
    provenance: Provenance | None = None
    # One-line human description (mirrors the spec's ``title``). Optional and purely
    # descriptive — surfaced by tooling (e.g. the network view's info card). Defaults
    # to "" so a manifest without it is still valid.
    title: str = ""

    def capability(self, capability_id: str) -> Capability | None:
        for c in self.capabilities:
            if c.id == capability_id:
                return c
        return None

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "weaver_id": self.weaver_id,
            "version": self.version,
            "capabilities": [c.to_json() for c in self.capabilities],
        }
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_json()
        if self.title:
            data["title"] = self.title
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> WeaverManifest:
        prov = data.get("provenance")
        return cls(
            weaver_id=data["weaver_id"],
            version=data["version"],
            capabilities=tuple(Capability.from_json(c) for c in data["capabilities"]),
            provenance=Provenance.from_json(prov) if prov is not None else None,
            title=data.get("title", ""),
        )
