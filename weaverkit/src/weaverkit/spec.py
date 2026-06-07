"""The weaver spec: the contract an agent fills in *before* writing any code.

A ``weaver.spec.toml`` declares what a weaver is — its source, license, identity,
the capabilities it offers (each consuming **registered shared keys** and grouping
its outputs), the backends it ships, and golden examples. ``load_spec`` parses it
with the stdlib ``tomllib`` (no dependency); ``validate_spec`` returns a list of
human-readable problems (empty == valid). The scaffold generator and conformance
checks both read this, so the spec is the single source of truth a weaver is built
*and verified* against.

See ``weaverkit/README.md`` for why this is TOML rather than YAML.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from weaverkit.keys import is_shared_key

_DB_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class SpecError(Exception):
    """A spec file is malformed at the structural level (cannot even be loaded).

    Value-level problems (an unregistered consume key, overlapping groups, …) are
    *not* exceptions — they come back from ``validate_spec`` as a list of strings,
    so an agent can see every problem at once instead of one-at-a-time.
    """


@dataclass(frozen=True)
class GroupSpec:
    """One output group: a set of outputs computed together (maps to OutputGroup)."""

    id: str
    outputs: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroupSpec:
        try:
            return cls(id=str(data["id"]), outputs=tuple(data["outputs"]))
        except KeyError as exc:
            raise SpecError(f"output group missing required key: {exc}") from None
        except TypeError as exc:
            raise SpecError(f"output group 'outputs' must be a list: {exc}") from None


@dataclass(frozen=True)
class CapabilitySpec:
    """One declared operation: consumes shared keys, produces grouped outputs."""

    id: str
    consumes: tuple[str, ...]
    groups: tuple[GroupSpec, ...]
    backends: tuple[str, ...] = ()
    max_batch_size: int | None = None
    cost: float = 1.0

    @property
    def produces(self) -> tuple[str, ...]:
        """Union of every group's outputs (what the capability emits externally)."""
        seen: list[str] = []
        for g in self.groups:
            for o in g.outputs:
                if o not in seen:
                    seen.append(o)
        return tuple(seen)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilitySpec:
        try:
            return cls(
                id=str(data["id"]),
                consumes=tuple(data["consumes"]),
                groups=tuple(GroupSpec.from_dict(g) for g in data.get("group", ())),
                backends=tuple(data.get("backends", ())),
                max_batch_size=data.get("max_batch_size"),
                cost=float(data.get("cost", 1.0)),
            )
        except KeyError as exc:
            raise SpecError(f"capability missing required key: {exc}") from None
        except TypeError as exc:
            raise SpecError(f"capability has a wrong-typed field: {exc}") from None


@dataclass(frozen=True)
class GoldenSpec:
    """A known input→output example, used by the conformance golden runner."""

    capability: str
    input: dict[str, Any]
    expect: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoldenSpec:
        try:
            return cls(
                capability=str(data["capability"]),
                input=dict(data["input"]),
                expect=dict(data["expect"]),
            )
        except KeyError as exc:
            raise SpecError(f"golden example missing required key: {exc}") from None
        except TypeError as exc:
            raise SpecError(f"golden 'input'/'expect' must be tables: {exc}") from None


@dataclass(frozen=True)
class WeaverSpec:
    """The whole contract for one weaver, loaded from ``weaver.spec.toml``."""

    db_name: str
    title: str
    version: str
    license: str
    source_url: str
    fingerprint_source: str
    source_sample: str
    backends: tuple[str, ...]
    capabilities: tuple[CapabilitySpec, ...]
    weaver_id: str = ""
    kind: str = "lookup"
    golden: tuple[GoldenSpec, ...] = field(default_factory=tuple)

    @property
    def package(self) -> str:
        """The Python package / workspace member name, e.g. ``madinweaver``."""
        return f"{self.db_name}weaver"

    @property
    def resolved_weaver_id(self) -> str:
        """Manifest ``weaver_id`` — explicit if set, else the db name."""
        return self.weaver_id or self.db_name

    def capability(self, capability_id: str) -> CapabilitySpec | None:
        for c in self.capabilities:
            if c.id == capability_id:
                return c
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeaverSpec:
        weaver = data.get("weaver", data)
        try:
            return cls(
                db_name=str(weaver["db_name"]),
                title=str(weaver["title"]),
                version=str(weaver["version"]),
                license=str(weaver["license"]),
                source_url=str(weaver["source_url"]),
                fingerprint_source=str(weaver["fingerprint_source"]),
                source_sample=str(weaver["source_sample"]),
                backends=tuple(weaver["backends"]),
                weaver_id=str(weaver.get("weaver_id", "")),
                kind=str(weaver.get("kind", "lookup")),
                capabilities=tuple(CapabilitySpec.from_dict(c) for c in data.get("capability", ())),
                golden=tuple(GoldenSpec.from_dict(g) for g in data.get("golden", ())),
            )
        except KeyError as exc:
            raise SpecError(f"spec missing required key: {exc}") from None
        except TypeError as exc:
            raise SpecError(f"spec has a wrong-typed field: {exc}") from None


def load_spec(path: str | Path) -> WeaverSpec:
    """Parse a ``weaver.spec.toml`` into a :class:`WeaverSpec`.

    Raises :class:`SpecError` if the file is missing or not parseable. Returns a
    spec object that may still be *invalid* — call :func:`validate_spec` on it.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SpecError(f"cannot read spec at {path}: {exc}") from None
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SpecError(f"{path} is not valid TOML: {exc}") from None
    return WeaverSpec.from_dict(data)


def validate_spec(spec: WeaverSpec) -> list[str]:
    """Return every problem with ``spec`` as a list of strings (empty == valid).

    Reports all problems at once rather than failing on the first, so an agent can
    fix the whole spec in one pass. Structural unloadable problems are raised as
    :class:`SpecError` by the loader instead; this checks *meaning*.
    """
    problems: list[str] = []

    # --- weaver-level fields -------------------------------------------------
    if not _DB_NAME_RE.match(spec.db_name):
        problems.append(
            f"db_name {spec.db_name!r} must match ^[a-z][a-z0-9_]*$ "
            "(lowercase, starts with a letter; the package becomes <db_name>weaver)"
        )
    if spec.weaver_id and not _DB_NAME_RE.match(spec.weaver_id):
        problems.append(f"weaver_id {spec.weaver_id!r} must match ^[a-z][a-z0-9_]*$")

    if spec.kind not in ("lookup", "resolver"):
        problems.append(
            f"kind {spec.kind!r} must be 'lookup' (clean id->data) or 'resolver' "
            "(fuzzy/ambiguous matching with candidates)"
        )

    for fieldname in ("title", "version", "license", "source_url"):
        if not str(getattr(spec, fieldname)).strip():
            problems.append(f"{fieldname} must be non-empty")

    if not spec.fingerprint_source.strip():
        problems.append("fingerprint_source must be non-empty (how is the data versioned?)")
    elif spec.fingerprint_source.strip().lower() == "unknown":
        problems.append(
            "fingerprint_source must not be 'unknown' — that silently disables "
            "cache invalidation; use a release tag, date, or checksum source"
        )

    if not spec.source_sample.strip():
        problems.append(
            "source_sample must be non-empty — paste a real snippet of the source data "
            "(a few rows / a record). This is the anti-hallucination guard: it proves the "
            "schema you map was observed, not invented."
        )

    if not spec.backends:
        problems.append("at least one backend must be declared (e.g. 'local' or 'api')")

    if not spec.capabilities:
        problems.append("at least one capability must be declared")

    # --- per-capability ------------------------------------------------------
    cap_ids: set[str] = set()
    for cap in spec.capabilities:
        where = f"capability {cap.id!r}" if cap.id else "an unnamed capability"
        if not cap.id:
            problems.append("a capability is missing an id")
        elif cap.id in cap_ids:
            problems.append(f"duplicate capability id {cap.id!r}")
        cap_ids.add(cap.id)

        if not cap.consumes:
            problems.append(f"{where}: consumes must be non-empty")
        for key in cap.consumes:
            if not is_shared_key(key):
                problems.append(
                    f"{where}: consumes {key!r}, which is not a registered shared key. "
                    "Use a key from weaverkit.keys.SHARED_KEYS (so the weaver is reachable), "
                    "or add the new bridge key to keys.py in this PR."
                )

        for b in cap.backends:
            if b not in spec.backends:
                problems.append(
                    f"{where}: backend {b!r} is not in the weaver's backends {list(spec.backends)}"
                )

        if not cap.groups:
            problems.append(f"{where}: must declare at least one output group")

        group_ids: set[str] = set()
        seen_outputs: dict[str, str] = {}
        for g in cap.groups:
            if not g.id:
                problems.append(f"{where}: an output group is missing an id")
            elif g.id in group_ids:
                problems.append(f"{where}: duplicate output group id {g.id!r}")
            group_ids.add(g.id)

            if not g.outputs:
                problems.append(f"{where}: output group {g.id!r} has no outputs")
            for o in g.outputs:
                if o in seen_outputs:
                    problems.append(
                        f"{where}: output {o!r} appears in both group "
                        f"{seen_outputs[o]!r} and {g.id!r} — outputs must be disjoint across groups"
                    )
                else:
                    seen_outputs[o] = g.id

        if not cap.produces:
            problems.append(f"{where}: produces nothing (groups have no outputs)")

    # --- golden examples -----------------------------------------------------
    for i, gold in enumerate(spec.golden):
        label = f"golden[{i}]"
        cap = spec.capability(gold.capability)
        if cap is None:
            problems.append(
                f"{label}: references capability {gold.capability!r}, which is not declared"
            )
            continue
        consumes = set(cap.consumes)
        produces = set(cap.produces)
        for k in gold.input:
            if k not in consumes:
                problems.append(
                    f"{label}: input key {k!r} is not in capability {cap.id!r} consumes "
                    f"{sorted(consumes)}"
                )
        for k in gold.expect:
            if k not in produces:
                problems.append(
                    f"{label}: expect key {k!r} is not in capability {cap.id!r} produces "
                    f"{sorted(produces)}"
                )

    return problems
