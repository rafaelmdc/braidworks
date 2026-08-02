"""Braider — finds routes through the capability graph and emits a serializable Braid.

MVP algorithm:
  1. Only single-input capabilities are in the graph.
  2. For each target type not already available, run Dijkstra from the available
     types to the target.
  3. Collect every (weaver_id, capability_id, input_type, output_type) edge used.
  4. Coalesce by (weaver_id, capability_id, input_type) into one invocation each.
  5. Topologically sort steps by data dependency.
  6. Assign backends per invocation by intersecting the policy with capability.backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from braidworks.core.braid import Braid, BackendPolicy, CapabilityInvocation
from braidworks.core.exceptions import NoPathError, NoPlanError
from braidworks.core.registry import BraidRegistry


def _without(
    graph: nx.MultiDiGraph, exclude: frozenset[tuple[str, str]]
) -> nx.MultiDiGraph:
    """A copy of ``graph`` with every excluded ``(weaver, capability)`` edge removed.

    On the multigraph this drops only the matching parallel edge(s); an interchangeable
    source on the same ``A→B`` pair survives, which is what lets a reroute switch onto it."""
    pruned = graph.copy()
    doomed = [
        (u, v, key)
        for u, v, key, data in graph.edges(keys=True, data=True)
        if (data["weaver_id"], data["capability_id"]) in exclude
    ]
    pruned.remove_edges_from(doomed)
    return pruned


def _best_edge(graph: nx.MultiDiGraph, u: str, v: str) -> dict:
    """The cheapest parallel ``u→v`` edge's data, ties broken stably by weaver then
    capability id, so a plan over interchangeable sources is deterministic."""
    parallels = graph.get_edge_data(u, v)  # {key: data}
    return min(
        parallels.values(),
        key=lambda d: (d["cost"], d["weaver_id"], d["capability_id"]),
    )


@dataclass
class _InvocationSpec:
    """Mutable accumulator before a CapabilityInvocation is finalized."""

    weaver_id: str
    capability_id: str
    input_type: str
    output_types: set[str] = field(default_factory=set)


class Braider:
    def __init__(self, registry: BraidRegistry) -> None:
        self._registry = registry

    def plan(
        self,
        available_types: frozenset[str],
        target_types: frozenset[str],
        *,
        backend_policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
        exclude: frozenset[tuple[str, str]] = frozenset(),
    ) -> Braid:
        """Route from ``available_types`` to ``target_types`` across the capability graph.

        ``exclude`` drops specific ``(weaver_id, capability_id)`` edges before routing —
        used to **re-plan around a failed node**: when a step errors mid-braid, the
        executor calls ``plan`` again with that capability excluded, so the planner finds
        an alternate path to the still-missing targets if the graph offers one.
        """
        graph = self._registry.build_graph()
        if exclude:
            graph = _without(graph, exclude)

        # 2–3. Route to each not-yet-available target and collect edges used.
        specs: dict[tuple[str, str, str], _InvocationSpec] = {}
        sources = frozenset(t for t in available_types if t in graph)
        for target in target_types:
            if target in available_types:
                continue  # already satisfied; no step needed
            path = self._route(graph, sources, target)
            for u, v in zip(path, path[1:]):
                data = _best_edge(graph, u, v)
                key = (data["weaver_id"], data["capability_id"], u)
                spec = specs.get(key)
                if spec is None:
                    spec = _InvocationSpec(data["weaver_id"], data["capability_id"], u)
                    specs[key] = spec
                spec.output_types.add(v)

        # 5. Order steps so each step's inputs are produced before it runs.
        ordered_specs = self._topological_order(list(specs.values()))

        # 6. Assign backends and build the final invocations.
        steps = tuple(
            self._build_invocation(spec, backend_policy) for spec in ordered_specs
        )

        all_inputs = frozenset(t for s in steps for t in s.input_types)
        all_outputs = frozenset(t for s in steps for t in s.output_types)
        return Braid(
            steps=steps,
            from_types=all_inputs - all_outputs,
            to_types=target_types,
        )

    def plan_capability(
        self,
        weaver_id: str,
        capability_id: str,
        *,
        backend_policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
    ) -> Braid:
        """Build a one-step braid for an *explicit* capability, bypassing routing.

        The type planner routes on types and never selects a capability whose
        produced types are already reachable — in particular a **self-loop**
        (``consumes == produces``, e.g. ``list_orthologs`` gene id -> gene ids).
        Traversal/fan-out (``--for-each`` / ``--traverse``) names the capability
        directly, so this constructs its invocation without going through Dijkstra.
        Requires a single-input capability (every fan capability is single-input).
        """
        cap = self._registry.get_capability(weaver_id, capability_id)
        if len(cap.consumes) != 1:
            raise NoPlanError(
                f"{weaver_id}.{capability_id}: traversal needs a single-input "
                f"capability, but it consumes {sorted(cap.consumes)}"
            )
        (source,) = tuple(cap.consumes)
        spec = _InvocationSpec(weaver_id, capability_id, source, set(cap.produces))
        invocation = self._build_invocation(spec, backend_policy)
        return Braid(
            steps=(invocation,),
            from_types=frozenset(cap.consumes),
            to_types=frozenset(cap.produces),
        )

    def _no_producer_message(self, target: str) -> str:
        """Explain a missing producer, distinguishing *absent* from *unconfigured*.

        A capability whose backends are all unconfigured is left out of its weaver's
        manifest, so the routing graph genuinely has no producer for its outputs. Saying
        only "no capability produces X" sends the reader looking for a capability to write,
        when one already exists and merely needs enabling — so name it when we can.
        """
        offers = [
            (manifest.weaver_id, unavailable)
            for manifest in self._registry.manifests()
            for unavailable in manifest.unavailable
            if target in unavailable.produces
        ]
        if not offers:
            return f"no capability produces {target!r}"
        listed = "; ".join(f"{weaver_id}:{u.describe()}" for weaver_id, u in offers)
        return (
            f"no *enabled* capability produces {target!r} — but it is produced by "
            f"{listed}. That capability is not registered because its backend is not "
            "configured, so enable the backend rather than adding a capability."
        )

    def _route(
        self, graph: nx.MultiDiGraph, sources: frozenset[str], target: str
    ) -> list[str]:
        if target not in graph:
            raise NoPathError(self._no_producer_message(target))
        if not sources:
            raise NoPathError(
                f"no available type can reach {target!r} (no source types in graph)"
            )
        try:
            _, path = nx.multi_source_dijkstra(
                graph, set(sources), target=target, weight="cost"
            )
        except nx.NetworkXNoPath:
            raise NoPathError(
                f"no route from available types to {target!r}"
            ) from None
        return path

    def _topological_order(
        self, specs: list[_InvocationSpec]
    ) -> list[_InvocationSpec]:
        if len(specs) <= 1:
            return specs
        dag = nx.DiGraph()
        dag.add_nodes_from(range(len(specs)))
        for i, consumer in enumerate(specs):
            for j, producer in enumerate(specs):
                if i != j and consumer.input_type in producer.output_types:
                    dag.add_edge(j, i)  # producer must run before consumer
        order = list(nx.topological_sort(dag))
        return [specs[i] for i in order]

    def _build_invocation(
        self, spec: _InvocationSpec, backend_policy: BackendPolicy
    ) -> CapabilityInvocation:
        cap = self._registry.get_capability(spec.weaver_id, spec.capability_id)

        # Intersect the policy preference with the capability's declared backends.
        filtered = [b for b in backend_policy.preference_order if b in cap.backends]
        if not filtered:
            raise NoPlanError(
                f"{spec.weaver_id}.{spec.capability_id}: policy {backend_policy.value} "
                f"yields no backend from declared {cap.backends}"
            )
        primary, *fallbacks = filtered
        fallback_backends = tuple(fallbacks)
        # Fallback conditions only matter when there is a backend to fall back to.
        fallback_on = (
            backend_policy.default_fallback_on if fallback_backends else frozenset()
        )
        return CapabilityInvocation(
            weaver_id=spec.weaver_id,
            capability_id=spec.capability_id,
            input_types=frozenset({spec.input_type}),
            output_types=frozenset(spec.output_types),
            primary_backend=primary,
            fallback_backends=fallback_backends,
            fallback_on=fallback_on,
        )
