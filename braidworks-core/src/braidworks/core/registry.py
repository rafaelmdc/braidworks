"""BraidRegistry — collects weavers and projects their capabilities into a graph.

Manual registration is the MVP path. Manifest validation runs at ``register()``
time (key invariant #19): an invalid manifest is rejected before any graph is
built. Only single-input capabilities are projected into the MVP graph
(invariant #24); multi-input capabilities are stored but never become edges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import warnings

import networkx as nx

from braidworks.core.capability import Capability, WeaverManifest
from braidworks.core.exceptions import (
    CapabilityUnavailableWarning,
    InvalidManifestError,
)

if TYPE_CHECKING:
    from braidworks.core.weaver import BaseWeaver


def validate_manifest(manifest: WeaverManifest) -> None:
    """Raise ``InvalidManifestError`` if the manifest violates any rule."""
    if not manifest.weaver_id:
        raise InvalidManifestError("weaver_id must be non-empty")
    if not manifest.version:
        raise InvalidManifestError(f"{manifest.weaver_id}: version must be non-empty")

    seen_capability_ids: set[str] = set()
    for cap in manifest.capabilities:
        if cap.id in seen_capability_ids:
            raise InvalidManifestError(
                f"{manifest.weaver_id}: duplicate capability id {cap.id!r}"
            )
        seen_capability_ids.add(cap.id)
        _validate_capability(manifest.weaver_id, cap)


def _validate_capability(weaver_id: str, cap: Capability) -> None:
    where = f"{weaver_id}.{cap.id}"
    if not cap.consumes:
        raise InvalidManifestError(f"{where}: consumes must be non-empty")
    if not cap.produces:
        raise InvalidManifestError(f"{where}: produces must be non-empty")
    if not cap.backends:
        raise InvalidManifestError(f"{where}: backends must be non-empty")
    if cap.max_batch_size is not None and cap.max_batch_size <= 0:
        raise InvalidManifestError(f"{where}: max_batch_size must be None or > 0")
    if cap.cost < 0:
        raise InvalidManifestError(f"{where}: cost must be >= 0")

    group_ids: set[str] = set()
    seen_outputs: set[str] = set()
    for group in cap.output_groups:
        if group.id in group_ids:
            raise InvalidManifestError(f"{where}: duplicate output group id {group.id!r}")
        group_ids.add(group.id)
        for out in group.outputs:
            if out not in cap.produces:
                raise InvalidManifestError(
                    f"{where}: output {out!r} in group {group.id!r} is not in produces"
                )
            if out in seen_outputs:
                raise InvalidManifestError(
                    f"{where}: output {out!r} appears in more than one output group"
                )
            seen_outputs.add(out)

    # Every produced type must appear in exactly one group — no gaps, no overlaps.
    missing = cap.produces - seen_outputs
    if missing:
        raise InvalidManifestError(
            f"{where}: produced types not assigned to any output group: {sorted(missing)}"
        )


class BraidRegistry:
    """Holds weavers + manifests and builds the projected capability graph."""

    def __init__(self) -> None:
        self._weavers: dict[str, BaseWeaver] = {}
        self._manifests: dict[str, WeaverManifest] = {}
        self._graph: nx.MultiDiGraph | None = None

    def register(self, weaver: BaseWeaver) -> None:
        """Validate and register a weaver instance. Raises ``InvalidManifestError``."""
        manifest = weaver.MANIFEST
        validate_manifest(manifest)
        if manifest.weaver_id in self._weavers:
            raise InvalidManifestError(
                f"weaver_id {manifest.weaver_id!r} is already registered"
            )
        self._weavers[manifest.weaver_id] = weaver
        self._manifests[manifest.weaver_id] = manifest
        self._graph = None  # invalidate cached projection
        if manifest.unavailable:
            listed = "; ".join(u.describe() for u in manifest.unavailable)
            warnings.warn(
                f"{manifest.weaver_id!r} registered without "
                f"{len(manifest.unavailable)} of its capabilities: {listed}. "
                "Requests for their outputs will fail as if no weaver produced them.",
                CapabilityUnavailableWarning,
                stacklevel=2,
            )

    def get_weaver(self, weaver_id: str) -> BaseWeaver:
        return self._weavers[weaver_id]

    def manifests(self) -> tuple[WeaverManifest, ...]:
        return tuple(self._manifests.values())

    def get_manifest(self, weaver_id: str) -> WeaverManifest | None:
        return self._manifests.get(weaver_id)

    def get_capability(self, weaver_id: str, capability_id: str) -> Capability:
        cap = self._manifests[weaver_id].capability(capability_id)
        if cap is None:
            raise KeyError(f"{weaver_id} has no capability {capability_id!r}")
        return cap

    def build_graph(self) -> nx.MultiDiGraph:
        """Project single-input capabilities into a directed type→type graph.

        Each single-input capability ``consumes={A}, produces={B, C}`` adds edges
        ``A→B`` and ``A→C``, annotated with ``(weaver_id, capability_id, cost)``.
        An **alternative-input** capability (``consumes_any``) treats its ``consumes`` as
        *alternatives* — any one suffices — so it adds an edge from *each* consumed type to
        each produced type (``consumes={A, B}, produces={C}`` → ``A→C`` and ``B→C``); the
        backend dispatches on whichever input is supplied. Plain multi-input (conjunctive)
        capabilities are skipped. The graph is a **multigraph**: when two
        capabilities offer the *same* ``A→B`` edge (interchangeable sources — e.g. two
        taxonomy resolvers ``organism.name → taxon.id``), both are kept as parallel
        edges. Routing takes the cheapest (Dijkstra minimizes over parallels), but the
        alternates survive so the executor can **reroute** onto one when the chosen
        source fails. (A single source is the common case; this is free until a second
        producer of the same edge appears.)
        """
        if self._graph is not None:
            return self._graph

        graph = nx.MultiDiGraph()
        for weaver_id, manifest in self._manifests.items():
            for cap in manifest.capabilities:
                # consumes_any => each consumed type is an independent edge source
                # (alternatives); a plain multi-input capability is conjunctive and not
                # routed by the type→type graph.
                if cap.consumes_any:
                    sources = tuple(cap.consumes)
                elif len(cap.consumes) == 1:
                    sources = tuple(cap.consumes)
                else:
                    continue
                for source in sources:
                    for target in cap.produces:
                        graph.add_edge(
                            source,
                            target,
                            weaver_id=weaver_id,
                            capability_id=cap.id,
                            cost=cap.cost,
                        )
        self._graph = graph
        return graph
