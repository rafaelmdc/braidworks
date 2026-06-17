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

from typing import Any

from braidworks.core.braid import BackendPolicy
from braidworks.core.cache import InMemoryStrandCache, StrandCache
from braidworks.core.exceptions import NoPathError, NoPlanError
from braidworks.core.executor import (
    ErrorPolicy,
    ExecutionResult,
    ExpandPolicy,
    LocalExecutor,
    ReviewPolicy,
)
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from braidworks.core.strand import MergePolicy, StrandSet


def relationship_name(capability_id: str) -> str:
    """The relationship noun for a fan capability id (``ncbi.list_orthologs`` ->
    ``orthologs``). Strips the weaver namespace and a leading ``list_``; an id that
    does not follow the convention falls back to its bare local name."""
    local = capability_id.rsplit(".", 1)[-1]
    return local[len("list_") :] if local.startswith("list_") else local


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


async def run_traversed(
    registry: BraidRegistry,
    input_sets: list[StrandSet],
    traversals: list[tuple[str, str]],
    target_types: frozenset[str],
    *,
    backend_policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
    expand_policy: ExpandPolicy = ExpandPolicy.all(),
    params: dict[str, dict[str, Any]] | None = None,
    review_policy: ReviewPolicy = ReviewPolicy.HALT,
    error_policy: ErrorPolicy = ErrorPolicy.RECORD_AND_CONTINUE,
    merge_policy: MergePolicy = MergePolicy.HIGHEST_CONFIDENCE,
    cache: StrandCache | None = None,
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
    braider = Braider(registry)
    cache = cache if cache is not None else InMemoryStrandCache()
    executor = LocalExecutor(registry, cache)
    params = params or {}

    final = ExecutionResult()
    current = input_sets

    async def _run(braid, sets, *, expand):
        return await executor.execute(
            braid,
            sets,
            review_policy=review_policy,
            error_policy=error_policy,
            merge_policy=merge_policy,
            expand_policy=expand,
            params=params,
        )

    for weaver_id, capability_id in traversals:
        if not current:
            break
        # The fan consumes one type (e.g. ncbi.taxon.id); the user's --have may be a
        # higher-level strand (organism.name) that has to be *resolved* down to it
        # first. The type planner does that for plain `weave`; do the same here by
        # running a resolution prelude before the fan, so `--traverse` accepts the
        # same natural inputs `weave` does. Re-root onto the prelude's resolved values.
        (source,) = tuple(registry.get_capability(weaver_id, capability_id).consumes)
        available = frozenset().union(*(s.available_types() for s in current))
        if source not in available:
            try:
                prelude = braider.plan(
                    available_types=available,
                    target_types=frozenset({source}),
                    backend_policy=backend_policy,
                )
            except (NoPlanError, NoPathError):
                prelude = None  # let the fan raise the precise missing-input error
            if prelude is not None and prelude.steps:
                # Resolution should not be truncated by a fan's --expand top:K.
                res = await _run(prelude, current, expand=ExpandPolicy.all())
                _absorb_dead_ends(final, res)
                # Feed the fan only the resolved join key — the prelude's byproduct
                # strands (e.g. the seed's scientific_name) must not ride into the
                # fanned children and stale-fill them.
                current = [s.restricted_to({source}) for s in res.resolved]
                if not current:
                    break
        braid = braider.plan_capability(
            weaver_id, capability_id, backend_policy=backend_policy
        )
        res = await _run(braid, current, expand=expand_policy)
        _absorb_dead_ends(final, res)
        current = res.resolved

    if target_types and current:
        available = frozenset().union(*(s.available_types() for s in current))
        try:
            braid = braider.plan(
                available_types=available,
                target_types=target_types,
                backend_policy=backend_policy,
            )
        except NoPlanError:
            raise
        res = await _run(braid, current, expand=expand_policy)
        final.references = _merge_references(final.references, res.references)
        final.resolved.extend(res.resolved)
        final.unresolved.extend(res.unresolved)
        final.review_queue.extend(res.review_queue)
        final.errors.extend(res.errors)
    else:
        # No target requested (or nothing survived): the fanned children are the result.
        final.resolved.extend(current)

    return final


def _absorb_dead_ends(final: ExecutionResult, res: ExecutionResult) -> None:
    """Carry a phase's non-resolved buckets + references into the final result.

    Resolved entities are *not* absorbed here — they flow on to the next phase and
    are bucketed by the final phase instead."""
    final.references = _merge_references(final.references, res.references)
    final.unresolved.extend(res.unresolved)
    final.review_queue.extend(res.review_queue)
    final.errors.extend(res.errors)


def _merge_references(existing, incoming):
    """Union references across phases, de-duplicated by weaver_id, order-stable."""
    seen = {r.weaver_id for r in existing}
    merged = list(existing)
    for r in incoming:
        if r.weaver_id not in seen:
            seen.add(r.weaver_id)
            merged.append(r)
    return merged
