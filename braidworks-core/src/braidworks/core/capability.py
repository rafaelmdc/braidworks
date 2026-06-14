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


PARAM_TYPES = frozenset({"string", "int", "float", "bool"})


@dataclass(frozen=True)
class Parameter:
    """A per-query knob a capability accepts beyond its input strands.

    Parameters are *refinements* (filters, sort, page size, thresholds), not
    identifiers — the planner never routes on them. A caller may pass values per
    run; an unset parameter falls back to ``default`` (so omitting every parameter
    reproduces the historical behaviour exactly). ``enum`` (when non-empty)
    restricts the accepted values. ``type`` is one of :data:`PARAM_TYPES` and drives
    coercion of string inputs (e.g. from the CLI).
    """

    name: str
    type: str = "string"
    enum: tuple[Any, ...] = ()
    default: Any = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.type not in PARAM_TYPES:
            raise ValueError(
                f"parameter {self.name!r}: unknown type {self.type!r} "
                f"(expected one of {sorted(PARAM_TYPES)})"
            )
        if self.enum and self.default is not None and self.default not in self.enum:
            raise ValueError(
                f"parameter {self.name!r}: default {self.default!r} not in enum "
                f"{list(self.enum)}"
            )

    def coerce(self, value: Any) -> Any:
        """Coerce a raw (possibly string, e.g. CLI) value to this parameter's type."""
        if value is None:
            return None
        try:
            if self.type == "int":
                return int(value)
            if self.type == "float":
                return float(value)
            if self.type == "bool":
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in ("1", "true", "yes", "on")
            return str(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"parameter {self.name!r}: cannot coerce {value!r} to {self.type}"
            ) from exc

    def validate(self, value: Any) -> Any:
        """Coerce ``value`` and check it against ``enum``; return the effective value."""
        coerced = self.coerce(value)
        if self.enum and coerced not in self.enum:
            raise ValueError(
                f"parameter {self.name!r}: {coerced!r} not in allowed values "
                f"{list(self.enum)}"
            )
        return coerced

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "enum": list(self.enum),
            "default": self.default,
            "description": self.description,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Parameter:
        return cls(
            name=data["name"],
            type=data.get("type", "string"),
            enum=tuple(data.get("enum", ())),
            default=data.get("default"),
            description=data.get("description", ""),
        )


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
    # Produced join keys that are intrinsically **one→many** (cardinality fan-out):
    # the strand carries a *list* of values, and the executor may fork the entity one
    # child per value (per ``ExpandPolicy``) so the braid continues for each. Must be a
    # subset of ``produces``. Empty (the default) means every output is scalar — the
    # historical behaviour, so nothing forks unless a weaver opts a key in.
    set_outputs: frozenset[str] = frozenset()
    # Per-query knobs this capability accepts (filters, sort, page size, thresholds).
    # Declarative, validated, and defaulted; the planner never routes on them. Empty
    # (the default) means the capability takes no parameters.
    parameters: tuple[Parameter, ...] = ()

    def __post_init__(self) -> None:
        extra = self.set_outputs - self.produces
        if extra:
            raise ValueError(
                f"set_outputs must be a subset of produces; unknown: {sorted(extra)}"
            )
        names = [p.name for p in self.parameters]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(
                f"capability {self.id!r}: duplicate parameter names: {sorted(dupes)}"
            )

    def resolve_params(self, given: dict[str, Any] | None) -> dict[str, Any]:
        """Validate caller params against the declaration and overlay defaults.

        Returns the *effective* params (declared defaults, with caller values
        validated/coerced on top). Raises ``ValueError`` on an unknown parameter
        name or a value outside an ``enum``. With no declared parameters and no
        caller values, returns ``{}`` — identical to the historical behaviour.
        """
        given = given or {}
        by_name = {p.name: p for p in self.parameters}
        unknown = set(given) - set(by_name)
        if unknown:
            raise ValueError(
                f"capability {self.id!r}: unknown parameter(s) {sorted(unknown)}; "
                f"accepted: {sorted(by_name)}"
            )
        effective: dict[str, Any] = {
            p.name: p.default for p in self.parameters if p.default is not None
        }
        for name, value in given.items():
            effective[name] = by_name[name].validate(value)
        return effective

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
            "set_outputs": sorted(self.set_outputs),
            "parameters": [p.to_json() for p in self.parameters],
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
            set_outputs=frozenset(data.get("set_outputs", ())),
            parameters=tuple(Parameter.from_json(p) for p in data.get("parameters", ())),
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
