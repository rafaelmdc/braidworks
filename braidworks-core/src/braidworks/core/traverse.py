"""Traversal fan-out — chain a weave *through* a same-type relationship.

The cardinality fan-out in the executor already chains automatically when a step
produces a set of a **different** type from the input (organism -> taxid ->
``list_genomes`` ⇒ each ``genome.accession`` -> ``describe_genome``). The one case
it cannot route is a **self-loop**: a capability that produces a set of the *same*
type it consumes — ``ncbi.list_orthologs`` takes a ``gene.ncbi.id`` and returns
more ``gene.ncbi.id``. The type planner never selects it (the target type is
already in hand) and the wave scheduler would co-schedule any downstream
``describe_gene`` with the seed gene instead of its orthologs.

This module makes that hop a first-class, *declarative* operation. The user names
the relationship (``--for-each orthologs``) or the capability (``--traverse
ncbi.list_orthologs``); we run it with fan-out, **re-root** the weave on each
produced value, and then plan the requested outputs from each child independently.
The seed is structurally gone (the fan overwrites each child's join key and marks
the parent terminal), so "describe each ortholog" means exactly that — no seed
contamination, and lineage (``parent_id``) regroups the children to the original
query.

A relationship name is the fan capability's id with a ``list_`` prefix stripped
(``ncbi.list_orthologs`` -> ``orthologs``), following the capability-naming
taxonomy (``resolve_`` / ``list_`` / ``describe_``). ``--traverse`` accepts the
full capability id directly and is the unambiguous escape hatch.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from braidworks.core.availability import require_capability
from braidworks.core.braid import BackendPolicy
from braidworks.core.cache import StrandCache
from braidworks.core.capability import Capability
from braidworks.core.exceptions import BackendUnavailable, NoPathError, NoPlanError
from braidworks.core.executor import (
    ErrorPolicy,
    ExecutionResult,
    ExpandPolicy,
    LocalExecutor,
    ReviewPolicy,
    _ExpansionBudget,
)
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from braidworks.core.strand import MergePolicy, StrandSet

_DEFAULT_EXPAND_POLICY = ExpandPolicy.all()


def relationship_name(capability_id: str) -> str:
    """The relationship noun for a fan capability id (``ncbi.list_orthologs`` ->
    ``orthologs``). Strips the weaver namespace and a leading ``list_``; an id that
    does not follow the convention falls back to its bare local name."""
    local = capability_id.rsplit(".", 1)[-1]
    return local.removeprefix("list_")


def fan_capabilities(registry: BraidRegistry) -> list[tuple[str, str, str]]:
    """Every fan (set-output) capability as ``(relationship, weaver_id, capability_id)``."""
    out: list[tuple[str, str, str]] = []
    for manifest in registry.manifests():
        for cap in manifest.capabilities:
            if cap.set_outputs:
                out.append((relationship_name(cap.id), manifest.weaver_id, cap.id))
    return out


def resolve_traversal(registry: BraidRegistry, token: str) -> tuple[str, str]:
    """Resolve a ``--for-each``/``--traverse`` token to ``(weaver_id, capability_id)``.

    ``token`` may be a relationship noun (``orthologs``) or a full capability id
    (``ncbi.list_orthologs``). Raises ``NoPlanError`` if nothing matches, if the
    match is not a fan capability, or if a relationship noun is ambiguous across
    weavers (the message points to the precise capability ids to disambiguate).
    """
    fans = fan_capabilities(registry)
    matches = [
        (wid, cid)
        for rel, wid, cid in fans
        if token == rel or token == cid or token == f"{wid}.{cid}"
    ]
    if not matches:
        declared = [
            (manifest.weaver_id, cap.id)
            for manifest in registry.declared_manifests()
            for cap in manifest.capabilities
            if cap.set_outputs
            and token in (relationship_name(cap.id), cap.id, f"{manifest.weaver_id}.{cap.id}")
        ]
        if len(declared) > 1:
            raise NoPlanError(f"relationship {token!r} is ambiguous: {sorted(declared)}")
        if declared:
            wid, cid = declared[0]
            try:
                require_capability(registry.get_weaver(wid), cid)
            except BackendUnavailable as exc:
                raise NoPlanError(str(exc)) from None
        # Distinguish "names a real capability but it doesn't fan" from "unknown".
        for manifest in registry.manifests():
            cap = manifest.capability(token)
            if cap is not None:
                raise NoPlanError(
                    f"{token!r} is not a fan capability (it has no set outputs to "
                    f"fan over). Traversal needs a list_* capability."
                )
        known = sorted({rel for rel, _, _ in fans})
        raise NoPlanError(
            f"no traversal relationship or capability named {token!r}. "
            f"Available relationships: {known or '(none)'}."
        )
    if len(matches) > 1:
        ids = ", ".join(f"{wid}.{cid}" if "." not in cid else cid for wid, cid in matches)
        raise NoPlanError(
            f"relationship {token!r} is ambiguous ({ids}); "
            f"use --traverse <capability-id> to pick one."
        )
    return matches[0]


def traversal_route_capabilities(
    registry: BraidRegistry,
    inputs: list[StrandSet],
    traversals: list[tuple[str, str]],
    targets: frozenset[str],
    *,
    backend_policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
) -> dict[str, Capability]:
    """Preview traversal, resolver-prelude and final-route parameter declarations.

    Failed previews are left to execution to report. This performs no backend I/O
    and never assumes a type present in one sparse row is available in every row.
    """
    capabilities = {cid: registry.get_capability(wid, cid) for wid, cid in traversals}
    braider = Braider(registry)

    def include_route(available, wanted):
        try:
            braid = braider.plan(available, wanted, backend_policy=backend_policy)
        except (NoPathError, NoPlanError):
            return
        for step in braid.steps:
            capabilities[step.capability_id] = registry.get_capability(
                step.weaver_id, step.capability_id
            )

    for available in dict.fromkeys(ss.available_types() for ss in inputs):
        for wid, cid in traversals:
            cap = registry.get_capability(wid, cid)
            if not cap.consumes <= available:
                include_route(available, cap.consumes)
            # A fan retains its consumed context alongside produced strands.
            # Other seed attributes were discarded at the re-rooting boundary.
            available = cap.consumes | cap.produces
        if targets:
            include_route(available, targets)
    return capabilities


async def run_traversed(
    registry: BraidRegistry,
    input_sets: list[StrandSet],
    traversals: list[tuple[str, str]],
    target_types: frozenset[str],
    *,
    backend_policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
    expand_policy: ExpandPolicy = _DEFAULT_EXPAND_POLICY,
    params: dict[str, dict[str, Any]] | None = None,
    review_policy: ReviewPolicy = ReviewPolicy.HALT,
    confidence_threshold: float = 0.0,
    error_policy: ErrorPolicy = ErrorPolicy.RECORD_AND_CONTINUE,
    merge_policy: MergePolicy = MergePolicy.HIGHEST_CONFIDENCE,
    cache: StrandCache | None = None,
    executor: LocalExecutor | None = None,
    max_expansion: int = 10_000,
    _expansion_budget: _ExpansionBudget | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    on_checkpoint: Callable[[Any], None] | None = None,
) -> ExecutionResult:
    """Run an ordered list of traversals, re-rooting between each, then plan ``want``.

    Phase ``i`` runs traversal ``i`` (a one-step fan braid) over the *resolved*
    children of phase ``i-1``, expanding one child per produced value. After the
    last traversal a final phase plans ``target_types`` from the children and runs
    it (skipped when ``target_types`` is empty — you just get the fanned entities).
    Non-resolved buckets (unresolved / review / errors) from every phase are carried
    into the returned result; only resolved entities flow to the next phase. A single
    cache is shared across phases so a value reached twice is computed once.
    """
    from braidworks.core.query import QueryOptions, QueryRequest, prepare_query
    from braidworks.core.query_state import continue_query, start_query

    prepared = prepare_query(
        registry,
        QueryRequest(
            tuple(input_sets),
            target_types,
            tuple(cid for _, cid in traversals),
            params or {},
            QueryOptions(
                backend_policy, expand_policy, review_policy, confidence_threshold, max_expansion
            ),
        ),
    )
    state = start_query(prepared, budget=_expansion_budget)
    state.settings_override = {
        "error_policy": error_policy.value,
        "merge_policy": merge_policy.value,
    }
    return await continue_query(
        registry,
        state,
        executor=executor,
        cache=cache if executor is None else None,
        on_event=on_event,
        on_checkpoint=on_checkpoint,
    )


def _absorb_dead_ends(final: ExecutionResult, res: ExecutionResult) -> None:
    """Carry a phase's non-resolved buckets + references into the final result.

    Resolved entities are *not* absorbed here — they flow on to the next phase and
    are bucketed by the final phase instead."""
    final.references = _merge_references(final.references, res.references)
    final.unresolved.extend(res.unresolved)
    final.review_queue.extend(res.review_queue)
    final.errors.extend(res.errors)
    final.truncations.extend(res.truncations)


def _merge_references(existing, incoming):
    """Union references across phases, de-duplicated by weaver_id, order-stable."""
    seen = {r.weaver_id for r in existing}
    merged = list(existing)
    for r in incoming:
        if r.weaver_id not in seen:
            seen.add(r.weaver_id)
            merged.append(r)
    return merged
