"""Executor data structures, policies, and the in-process LocalExecutor."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from itertools import islice, product
from math import prod
from typing import TYPE_CHECKING, Any

from braidworks.core.braid import (
    BackendPolicy,
    Braid,
    CapabilityInvocation,
    FallbackCondition,
)
from braidworks.core.cache import StrandCache, compute_cache_key
from braidworks.core.capability import Capability
from braidworks.core.errors import ErrorCategory, classify_error
from braidworks.core.exceptions import (
    BackendConfigurationError,
    BackendUnavailable,
    BraidworksError,
    NoPathError,
    NoPlanError,
    ReviewRequired,
)
from braidworks.core.references import Reference, references_for_braid
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import CandidateResult, WeaveResult, WeaveStatus
from braidworks.core.runner import InProcessStepRunner, WeaveStepRunner, validate_batch_size
from braidworks.core.strand import MergePolicy, StepOutcome, Strand, StrandSet, entity_key

if TYPE_CHECKING:
    from braidworks.core.execution_state import ExecutionState

logger = logging.getLogger(__name__)


class ExpandMode(Enum):
    """How a one→many step (cardinality fan-out) resolves its alternatives."""

    TOP = "top"  # collapse to the single best representative (default)
    TOP_K = "top_k"  # fork the best ``k`` into independent children
    ALL = "all"  # fork every alternative into an independent child


@dataclass(frozen=True)
class ExpandPolicy:
    """Cardinality knob for fan-out, sitting beside ``BackendPolicy`` / ``ReviewPolicy``.

    Governs what the executor does when a step yields several successors (today: a
    resolver's ``candidates`` / an ``AMBIGUOUS`` result). ``TOP`` contracts to one;
    ``TOP_K``/``ALL`` expand the braid, continuing it per child. The default is
    ``TOP`` so existing single-result runs are unaffected.
    """

    mode: ExpandMode = ExpandMode.TOP
    k: int = 1

    @classmethod
    def top(cls) -> ExpandPolicy:
        return cls(ExpandMode.TOP, 1)

    @classmethod
    def top_k(cls, k: int) -> ExpandPolicy:
        if k < 1:
            raise ValueError("ExpandPolicy.top_k requires k >= 1")
        return cls(ExpandMode.TOP_K, k)

    @classmethod
    def all(cls) -> ExpandPolicy:
        return cls(ExpandMode.ALL, 0)

    def fork_count(self, n: int) -> int:
        """How many of ``n`` available alternatives to materialize as children."""
        if self.mode is ExpandMode.TOP:
            return 1
        if self.mode is ExpandMode.TOP_K:
            return min(self.k, n)
        return n  # ALL


_DEFAULT_EXPAND_POLICY = ExpandPolicy()


class ReviewPolicy(Enum):
    """What the executor does on ``OK + requires_review`` or a low-confidence result.

    ``HALT`` queues ambiguity before any candidate selection or expansion.
    ``ALLOW_CONTINUE`` explicitly permits selection while preserving review flags.
    An explicit confidence threshold still pauses below-threshold results.
    ``RAISE`` rejects ambiguity or review immediately. Candidate-free ambiguity
    queues unless RAISE is selected.
    """

    HALT = "halt"  # stop the chain, queue with remaining steps (default)
    ALLOW_CONTINUE = "allow_continue"  # merge strands and continue
    RAISE = "raise"  # raise ReviewRequired immediately


class ErrorPolicy(Enum):
    """What the executor does on ``WeaveStatus.ERROR`` after fallbacks are exhausted."""

    RECORD_AND_CONTINUE = "record_and_continue"  # add to errors, drop entity, continue
    RAISE = "raise"  # raise immediately; no ExecutionResult returned


@dataclass
class ReviewQueueItem:
    """A halted entity carrying everything needed to resume after human review."""

    strand_set: StrandSet
    triggering_result: WeaveResult
    remaining_steps: tuple[CapabilityInvocation, ...]
    continuation: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "strand_set": self.strand_set.to_json(),
            "triggering_result": self.triggering_result.to_json(),
            "remaining_steps": [s.to_json() for s in self.remaining_steps],
            **({"continuation": self.continuation} if self.continuation else {}),
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ReviewQueueItem:
        return cls(
            strand_set=StrandSet.from_json(data["strand_set"]),
            triggering_result=WeaveResult.from_json(data["triggering_result"]),
            remaining_steps=tuple(
                CapabilityInvocation.from_json(s) for s in data["remaining_steps"]
            ),
            continuation=dict(data.get("continuation", {})),
        )


@dataclass
class ExecutionError:
    """A structural/technical failure captured without a raw Exception object.

    ``category`` buckets the failure (upstream 5xx, rate-limit, timeout, …) so callers
    get a plain-English reason instead of a raw message. ``recovered`` is set when the
    executor rerouted around this failed node and reached the targets another way — the
    error is then a *report*, not a fatal outcome (the entity is among ``resolved``)."""

    strand_set: StrandSet
    error_type: str
    message: str
    step_index: int | None = None  # None = preflight failure
    capability_id: str | None = None  # None = preflight failure
    category: ErrorCategory = ErrorCategory.UNKNOWN
    recovered: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "strand_set": self.strand_set.to_json(),
            "error_type": self.error_type,
            "message": self.message,
            "step_index": self.step_index,
            "capability_id": self.capability_id,
            "category": self.category.value,
            "recovered": self.recovered,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ExecutionError:
        return cls(
            strand_set=StrandSet.from_json(data["strand_set"]),
            error_type=data["error_type"],
            message=data["message"],
            step_index=data.get("step_index"),
            capability_id=data.get("capability_id"),
            category=ErrorCategory(data.get("category", "unknown")),
            recovered=data.get("recovered", False),
        )


@dataclass(frozen=True)
class ExpansionTruncation:
    """A bounded fork's omitted alternatives, before downstream expansion.

    Counts describe this capability's selected fan, not hypothetical final leaves.
    Labels may repeat; source_row identifies a supplied input ordinal when present.
    """

    entity_id: str
    source_row: int | None
    capability_id: str
    requested: int
    kept: int
    limit: int

    @property
    def omitted(self) -> int:
        return self.requested - self.kept

    def to_json(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "source_row": self.source_row,
            "capability_id": self.capability_id,
            "requested": self.requested,
            "kept": self.kept,
            "omitted": self.omitted,
            "limit": self.limit,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ExpansionTruncation:
        return cls(
            data["entity_id"],
            data.get("source_row"),
            data["capability_id"],
            data["requested"],
            data["kept"],
            data["limit"],
        )


@dataclass
class _ExpansionBudget:
    """Reserved leaf slots shared by chunks, traversal phases and reroutes."""

    limit: int
    leaves: int
    next_identity: int = 0

    def identify(self, ss: StrandSet) -> None:
        if ss.execution_key is None:
            ss.execution_key = f"node:{self.next_identity}"
            self.next_identity += 1
        elif ss.execution_key.startswith("node:"):
            self.next_identity = max(self.next_identity, int(ss.execution_key.split(":", 1)[1]) + 1)

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit < 1:
            raise ValueError("max_expansion must be a positive integer")
        if (
            type(self.leaves) is not int
            or self.leaves < 0
            or type(self.next_identity) is not int
            or self.next_identity < 0
        ):
            raise ValueError("Invalid expansion/identity counters")

    def reserve(
        self, requested: int, ss: StrandSet, capability_id: str, result: ExecutionResult
    ) -> int:
        # The parent's slot is replaced, so at least one successor always fits.
        kept = min(requested, max(1, self.limit - self.leaves + 1))
        self.leaves += kept - 1
        if kept < requested:
            truncation = ExpansionTruncation(
                ss.entity_id, ss.source_row, capability_id, requested, kept, self.limit
            )
            result.truncations.append(truncation)
            ss.warnings.append(
                f"expansion limit {self.limit}: kept {kept} of {requested} successors at {capability_id}"
            )
        return kept


@dataclass
class ExecutionResult:
    """Terminal entity outcomes and branch diagnostics for a batch.

    ``errors`` includes diagnostics for otherwise-resolved entities as well as
    fatal failures. JSON carries result-scoped entity references so these links
    survive serialization without assuming user-supplied IDs are unique.
    """

    resolved: list[StrandSet] = field(default_factory=list)
    unresolved: list[tuple[StrandSet, WeaveResult]] = field(default_factory=list)
    review_queue: list[ReviewQueueItem] = field(default_factory=list)
    errors: list[ExecutionError] = field(default_factory=list)
    # Citations for the sources this run drew on, ordered by weaver_id (issue #1).
    # Derived from the executed braid's weavers; empty when none carry provenance.
    references: list[Reference] = field(default_factory=list)
    truncations: list[ExpansionTruncation] = field(default_factory=list)

    def total(self) -> int:
        """Count distinct terminal entities (fan-out leaves, not input roots).

        Several branch errors can describe one failed entity; recovered errors
        are diagnostics, not additional terminal outcomes.
        """
        terminal = (
            self.resolved
            + [ss for ss, _ in self.unresolved]
            + [item.strand_set for item in self.review_queue]
            + [error.strand_set for error in self.errors if not error.recovered]
        )
        return len({entity_key(ss) for ss in terminal})

    def _entity_buckets(self) -> dict[str, list[StrandSet]]:
        return {
            "resolved": self.resolved,
            "unresolved": [ss for ss, _ in self.unresolved],
            "review_queue": [item.strand_set for item in self.review_queue],
            "errors": [error.strand_set for error in self.errors],
        }

    def fatal_errors(self) -> list[ExecutionError]:
        """Errors that actually blocked an entity — i.e. were not recovered by a reroute
        and whose entity reached none of its targets. A failure on one branch of an
        otherwise-resolved entity (partial success) is reported but *not* fatal, so a
        caller can exit non-zero only when the request truly could not be met."""
        resolved_ids = {entity_key(ss) for ss in self.resolved}
        return [
            e
            for e in self.errors
            if not e.recovered and entity_key(e.strand_set) not in resolved_ids
        ]

    def to_json(self) -> dict[str, Any]:
        # References encode object relationships, not entity_id labels. Their
        # deterministic numbering is local to this result, without global IDs.
        references: dict[int, int] = {}
        entity_refs: dict[str, list[int]] = {}
        for bucket, entities in self._entity_buckets().items():
            entity_refs[bucket] = [
                references.setdefault(id(ss), len(references)) for ss in entities
            ]
        return {
            "resolved": [ss.to_json() for ss in self.resolved],
            "unresolved": [[ss.to_json(), wr.to_json()] for ss, wr in self.unresolved],
            "review_queue": [item.to_json() for item in self.review_queue],
            "errors": [e.to_json() for e in self.errors],
            "references": [r.to_json() for r in self.references],
            "entity_refs": entity_refs,
            "truncations": [item.to_json() for item in self.truncations],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ExecutionResult:
        result = cls(
            resolved=[StrandSet.from_json(ss) for ss in data.get("resolved", [])],
            unresolved=[
                (StrandSet.from_json(ss), WeaveResult.from_json(wr))
                for ss, wr in data.get("unresolved", [])
            ],
            review_queue=[ReviewQueueItem.from_json(item) for item in data.get("review_queue", [])],
            errors=[ExecutionError.from_json(e) for e in data.get("errors", [])],
            references=[Reference.from_json(r) for r in data.get("references", [])],
            truncations=[
                ExpansionTruncation.from_json(item) for item in data.get("truncations", [])
            ],
        )
        if "entity_refs" not in data:
            # Legacy snapshots did not preserve aliases. Keep them readable;
            # guessing links by label/content would conflate duplicate inputs.
            return result
        entity_refs = data["entity_refs"]
        if not isinstance(entity_refs, dict):
            raise TypeError("entity_refs must be a mapping of buckets to references")
        entities_by_ref: dict[int, StrandSet] = {}
        buckets: dict[str, list[StrandSet]] = {}
        for bucket, entities in result._entity_buckets().items():
            refs = entity_refs.get(bucket)
            if not isinstance(refs, list) or len(refs) != len(entities):
                raise ValueError(f"entity_refs.{bucket} must match its bucket length")
            restored: list[StrandSet] = []
            for ref, ss in zip(refs, entities, strict=True):
                if type(ref) is not int or ref < 0:
                    raise ValueError("entity references must be non-negative integers")
                existing = entities_by_ref.setdefault(ref, ss)
                if existing != ss:
                    raise ValueError(f"conflicting entity snapshots for reference {ref}")
                restored.append(existing)
            buckets[bucket] = restored
        result.resolved = buckets["resolved"]
        result.unresolved = [
            (ss, wr) for ss, (_, wr) in zip(buckets["unresolved"], result.unresolved, strict=True)
        ]
        for ss, item in zip(buckets["review_queue"], result.review_queue, strict=True):
            item.strand_set = ss
        for ss, error in zip(buckets["errors"], result.errors, strict=True):
            error.strand_set = ss
        return result


class LocalExecutor:
    """Runs a Braid against a list of StrandSets in-process with asyncio.

    Terminal entities appear in resolved, unresolved, review_queue or fatal
    errors. Branch diagnostics can also accompany successful entities. Fan-out
    counts terminal children rather than their input roots. A RAISE policy or
    ``BackendConfigurationError`` can abort the whole run.
    """

    def __init__(
        self,
        registry: BraidRegistry,
        cache: StrandCache | None = None,
        *,
        runner: WeaveStepRunner | None = None,
    ) -> None:
        from braidworks.core.cache import InMemoryStrandCache

        self._registry = registry
        self._cache: StrandCache = cache if cache is not None else InMemoryStrandCache()
        # The seam: how a single weave-step batch actually executes. Default is
        # in-process (historical behavior); a distributed runner can be injected to
        # dispatch steps to workers without changing any orchestration below.
        self._runner: WeaveStepRunner = (
            runner if runner is not None else InProcessStepRunner(registry)
        )

    async def execute(
        self,
        braid: Braid,
        strand_sets: list[StrandSet],
        *,
        review_policy: ReviewPolicy = ReviewPolicy.HALT,
        error_policy: ErrorPolicy = ErrorPolicy.RECORD_AND_CONTINUE,
        merge_policy: MergePolicy = MergePolicy.HIGHEST_CONFIDENCE,
        expand_policy: ExpandPolicy = _DEFAULT_EXPAND_POLICY,
        expand_by_type: dict[str, ExpandPolicy] | None = None,
        params: dict[str, dict[str, Any]] | None = None,
        confidence_threshold: float = 0.0,
        chunk_size: int = 10_000,
        max_expansion: int = 10_000,
        backend_policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
        reroute: bool = True,
        on_event: Callable[[dict], None] | None = None,
        _expansion_budget: _ExpansionBudget | None = None,
        on_checkpoint: Callable[[Any], None] | None = None,
    ) -> ExecutionResult:
        state = self.start_state(
            braid,
            strand_sets,
            review_policy=review_policy,
            error_policy=error_policy,
            merge_policy=merge_policy,
            expand_policy=expand_policy,
            expand_by_type=expand_by_type,
            params=params,
            confidence_threshold=confidence_threshold,
            chunk_size=chunk_size,
            max_expansion=max_expansion,
            backend_policy=backend_policy,
            reroute=reroute,
            _expansion_budget=_expansion_budget,
        )
        return await self.continue_state(state, on_event=on_event, on_checkpoint=on_checkpoint)

    def start_state(
        self,
        braid,
        strand_sets,
        *,
        review_policy=ReviewPolicy.HALT,
        error_policy=ErrorPolicy.RECORD_AND_CONTINUE,
        merge_policy=MergePolicy.HIGHEST_CONFIDENCE,
        expand_policy=_DEFAULT_EXPAND_POLICY,
        expand_by_type=None,
        params=None,
        confidence_threshold=0.0,
        chunk_size=10_000,
        max_expansion=10_000,
        backend_policy=BackendPolicy.LOCAL_FIRST,
        reroute=True,
        _expansion_budget=None,
    ):
        """Create a serializable state without source I/O; execute remains the legacy facade."""
        from braidworks.core.execution_state import ExecutionState

        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if type(chunk_size) is not int or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer")
        budget = _expansion_budget or _ExpansionBudget(max_expansion, len(strand_sets))
        for ss in strand_sets:
            budget.identify(ss)
        settings = {
            "review_policy": review_policy.value,
            "error_policy": error_policy.value,
            "merge_policy": merge_policy.value,
            "expand": expand_policy.mode.value,
            "k": expand_policy.k,
            "expand_by_type": {
                key: {"mode": value.mode.value, "k": value.k}
                for key, value in (expand_by_type or {}).items()
            },
            "params": params or {},
            "confidence_threshold": confidence_threshold,
            "chunk_size": chunk_size,
            "backend_policy": backend_policy.value,
            "reroute": reroute,
        }
        return ExecutionState(braid, strand_sets, settings, budget)

    async def continue_state(
        self, state: ExecutionState, *, on_event=None, on_checkpoint=None
    ) -> ExecutionResult:
        """Continue a value snapshot after fully applied waves; no source replay before its cursor."""
        from braidworks.core.execution_state import ExecutionState
        from braidworks.core.planner import Braider

        if state.in_wave:
            raise ValueError("Load the last checkpoint after an interrupted/unapplied wave")
        settings = state.settings
        options = {
            "review_policy": ReviewPolicy(settings["review_policy"]),
            "error_policy": ErrorPolicy(settings["error_policy"]),
            "merge_policy": MergePolicy(settings["merge_policy"]),
            "expand_policy": ExpandPolicy(ExpandMode(settings["expand"]), settings["k"]),
            "expand_by_type": {
                key: ExpandPolicy(ExpandMode(value["mode"]), value["k"])
                for key, value in settings["expand_by_type"].items()
            },
            "params": settings["params"],
            "confidence_threshold": settings["confidence_threshold"],
            "expansion_budget": state.budget,
            "on_event": on_event,
        }

        def checkpoint():
            if on_checkpoint is not None:
                on_checkpoint(state)

        if not state.initialized:
            state.result.references = list(references_for_braid(state.braid, self._registry))
            for ss in state.inputs:
                missing = state.braid.from_types - ss.available_types()
                if missing:
                    state.result.errors.append(
                        ExecutionError(
                            ss,
                            "MissingInputError",
                            f"missing required input types: {sorted(missing)}",
                            category=ErrorCategory.INPUT,
                        )
                    )
                else:
                    state.survivors.append(ss)
            state.initialized = True
            checkpoint()
        if state.stage == "chunks":
            while state.chunk_start < len(state.survivors):
                chunk = state.survivors[
                    state.chunk_start : state.chunk_start + settings["chunk_size"]
                ]
                await self._run_chunk(
                    state.braid,
                    chunk,
                    state.result,
                    reroute_out=state.reroute_candidates if settings["reroute"] else None,
                    state=state,
                    checkpoint=checkpoint,
                    **options,
                )
                state.chunk_start += len(chunk)
                state.chunk_active = False
                state.live = []
                checkpoint()
            state.stage = "reroute"
            checkpoint()
        if state.stage == "reroute":
            while state.reroute_index < len(state.reroute_candidates):
                ss, failed = state.reroute_candidates[state.reroute_index]
                missing = state.braid.to_types - ss.available_types()
                if not missing:
                    state.result.resolved.append(ss)
                    _flag_recovered(state.result, ss)
                else:
                    if state.reroute_state is None:
                        try:
                            alt = Braider(self._registry).plan(
                                ss.available_types(),
                                missing,
                                backend_policy=BackendPolicy(settings["backend_policy"]),
                                exclude=failed,
                            )
                        except (NoPathError, NoPlanError):
                            alt = None
                        if alt is not None:
                            state.reroute_state = ExecutionState(
                                alt, [ss], {**settings, "reroute": False}, state.budget
                            )
                    if state.reroute_state is not None:
                        sub = await self.continue_state(
                            state.reroute_state,
                            on_event=on_event,
                            on_checkpoint=lambda _: checkpoint(),
                        )
                        for bucket in (
                            "resolved",
                            "unresolved",
                            "review_queue",
                            "errors",
                            "truncations",
                        ):
                            getattr(state.result, bucket).extend(getattr(sub, bucket))
                        refs = {
                            ref.weaver_id: ref for ref in state.result.references + sub.references
                        }
                        state.result.references = [refs[key] for key in sorted(refs)]
                        if sub.resolved:
                            _flag_recovered(state.result, ss)
                state.reroute_state = None
                state.reroute_index += 1
                checkpoint()
            state.stage = "done"
            checkpoint()
        return state.result

    async def _run_chunk(
        self,
        braid: Braid,
        chunk: list[StrandSet],
        result: ExecutionResult,
        *,
        review_policy: ReviewPolicy,
        error_policy: ErrorPolicy,
        merge_policy: MergePolicy,
        expand_policy: ExpandPolicy,
        expand_by_type: dict[str, ExpandPolicy],
        params: dict[str, dict[str, Any]],
        confidence_threshold: float,
        expansion_budget: _ExpansionBudget,
        reroute_out: list[tuple[StrandSet, frozenset[tuple[str, str]]]] | None = None,
        on_event: Callable[[dict], None] | None = None,
        state: ExecutionState,
        checkpoint=None,
    ) -> None:
        if not state.chunk_active:
            state.live = list(chunk)
            state.terminal = set()
            state.representative = {}
            state.errored = {
                entity_key(ss): {
                    tuple(pair)
                    for pair in state.settings.get("prior_errors", {}).get(entity_key(ss), [])
                }
                for ss in chunk
                if state.settings.get("prior_errors", {}).get(entity_key(ss))
            }
            state.wave_index = 0
            state.chunk_active = True
        live = state.live
        representative = state.representative
        errored = state.errored
        waves = braid.waves()

        for wi in range(state.wave_index, len(waves)):
            wave = waves[wi]
            if not live:
                break
            # Children spawned by fan-out this wave; folded into ``live`` afterwards so
            # they flow through the remaining waves alongside un-forked entities.
            # Steps in a wave are independent → run them concurrently. Each job only
            # awaits I/O and never mutates an entity, so results are merged afterwards
            # in deterministic step order (no shared-state hazard across the gather).
            state.in_wave = True
            jobs = [self._run_step_over(braid, si, live, params) for si in wave]
            wave_results = await asyncio.gather(*jobs)
            # Live progress hook (e.g. weaverkit serve's light-up): one event per wave as
            # its steps finish, naming the capabilities that ran. Off by default.
            if on_event is not None:
                on_event(
                    {
                        "wave": wi,
                        "capabilities": [inv.capability_id for _si, inv, _outs in wave_results],
                    }
                )
            remaining_steps = tuple(braid.steps[si] for later in waves[wi + 1 :] for si in later)
            self._apply_wave(
                state,
                wave_results,
                remaining_steps,
                review_policy=review_policy,
                error_policy=error_policy,
                merge_policy=merge_policy,
                expand_policy=expand_policy,
                expand_by_type=expand_by_type,
                confidence_threshold=confidence_threshold,
                expansion_budget=expansion_budget,
            )
            live = state.live
            state.wave_index = wi + 1
            state.in_wave = False
            if checkpoint is not None:
                checkpoint()

        # Survivors: resolved if any requested target type was produced (branches are
        # best-effort enrichment — empty branches are recorded in completion, not a
        # failure). An entity that reached no target *and* errored on a branch is a
        # reroute candidate (try an alternate path) — failing that it stays reported by
        # its already-recorded ExecutionError; one that merely came up empty is unresolved.
        for ss in live:
            if braid.to_types & ss.available_types():
                result.resolved.append(ss)  # may carry a reported error on a failed branch
            elif entity_key(ss) in errored:
                if reroute_out is not None:
                    reroute_out.append((ss, frozenset(errored[entity_key(ss)])))
                # else already reported via its ExecutionError(s) in result.errors
            else:
                rep = representative.get(entity_key(ss)) or self._synth_no_match(braid)
                result.unresolved.append((ss, rep))

    def _apply_wave(
        self,
        state,
        wave_results,
        remaining_steps,
        *,
        review_policy,
        error_policy,
        merge_policy,
        expand_policy,
        expand_by_type,
        confidence_threshold,
        expansion_budget,
    ):
        """Deterministic transition over fetched values; performs no source/cache I/O."""
        live = state.live
        result = state.result
        terminal = state.terminal
        representative = state.representative
        errored = state.errored
        spawned = []
        ordered = sorted(wave_results, key=lambda t: t[0])
        for step_index, invocation, outs in ordered:
            cap = self._registry.get_capability(invocation.weaver_id, invocation.capability_id)
            for ss, kind, payload in outs:
                if entity_key(ss) in terminal:
                    continue
                if kind == "skipped":
                    ss.completion.append(StepOutcome(invocation.capability_id, "", "skipped"))
                    continue
                if kind == "satisfied":
                    produced = tuple(sorted(invocation.output_types & ss.available_types()))
                    ss.completion.append(StepOutcome(invocation.capability_id, "", "ok", produced))
                    continue
                review_count = len(result.review_queue)
                pending = tuple(inv for si, inv, _ in ordered if si > step_index) + remaining_steps
                self._apply_result(
                    ss,
                    payload,
                    step_index,
                    invocation,
                    cap.set_outputs,
                    pending,
                    result,
                    terminal,
                    representative,
                    spawned,
                    errored,
                    review_policy=review_policy,
                    error_policy=error_policy,
                    merge_policy=merge_policy,
                    expand_policy=expand_policy,
                    expand_by_type=expand_by_type,
                    confidence_threshold=confidence_threshold,
                    expansion_budget=expansion_budget,
                )
                for item in result.review_queue[review_count:]:
                    item.continuation.update(
                        invocation=invocation.to_json(),
                        to_types=sorted(state.braid.to_types),
                        prior_errors=[
                            list(pair) for pair in sorted(errored.get(entity_key(ss), set()))
                        ],
                    )

        if terminal:
            live = [ss for ss in live if entity_key(ss) not in terminal]
        if spawned:
            live.extend(spawned)
        state.live = live

    async def _run_step_over(
        self,
        braid: Braid,
        step_index: int,
        entities: list[StrandSet],
        params: dict[str, dict[str, Any]],
    ) -> tuple[int, CapabilityInvocation, list[tuple[StrandSet, str, WeaveResult | None]]]:
        """Run one step over the entities that can take it; collect, don't mutate.

        Returns ``(step_index, invocation, outs)`` where each ``out`` is
        ``(entity, kind, payload)`` with ``kind`` in ``{"skipped", "satisfied",
        "result"}`` (payload is the WeaveResult only for ``"result"``). An entity is
        ``"skipped"`` when it lacks the step's input types (an upstream branch did not
        produce them) and ``"satisfied"`` when the step's outputs are already present.
        """
        invocation = braid.steps[step_index]
        weaver = self._registry.get_weaver(invocation.weaver_id)
        cap = self._registry.get_capability(invocation.weaver_id, invocation.capability_id)
        requested = invocation.output_types
        triggered = cap.triggered_groups(requested)
        manifest_version = weaver.MANIFEST.version
        primary_fingerprint = weaver.backend_fingerprint(invocation.primary_backend)
        # Validate/default this step's params once (raises on an unknown name / bad enum).
        effective_params = cap.resolve_params(params.get(invocation.capability_id))

        outs: list[tuple[StrandSet, str, WeaveResult | None]] = []
        misses: list[StrandSet] = []
        for ss in entities:
            if not invocation.input_types <= ss.available_types():
                outs.append((ss, "skipped", None))
                continue
            if requested <= ss.available_types():
                outs.append((ss, "satisfied", None))
                continue
            key = compute_cache_key(
                cap,
                ss,
                weaver_id=invocation.weaver_id,
                weaver_version=manifest_version,
                backend=invocation.primary_backend,
                backend_fingerprint=primary_fingerprint,
                params=effective_params,
            )
            cached = self._cache.get(key, triggered)
            if cached is not None:
                outs.append((ss, "result", cached))
            else:
                misses.append(ss)

        if misses:
            miss_results = await self._resolve_misses(cap, invocation, misses, effective_params)
            for ss, r in zip(misses, miss_results):
                if r.status is not WeaveStatus.ERROR:
                    # Internal computation alone does not make a group reusable:
                    # shared mappers deliberately omit unrequested group strands.
                    # Keep triggered groups even when optional values are absent,
                    # and retain richer groups actually emitted by custom weavers.
                    payloads = [r.strands]
                    if r.status is WeaveStatus.AMBIGUOUS and r.candidates:
                        payloads = [candidate.strands for candidate in r.candidates]
                    emitted_groups = frozenset(
                        group.id
                        for group in cap.output_groups
                        if all(
                            any(strand.type_id in group.outputs for strand in payload)
                            for payload in payloads
                        )
                    )
                    cached_result = replace(
                        r, computed_groups=r.computed_groups & (triggered | emitted_groups)
                    )
                    # Cache every non-error result (incl. NO_MATCH/AMBIGUOUS), keyed by
                    # the backend that produced it, so a second pass is a hit.
                    self._cache.put(
                        compute_cache_key(
                            cap,
                            ss,
                            weaver_id=invocation.weaver_id,
                            weaver_version=r.weaver_version,
                            backend=r.backend_used,
                            backend_fingerprint=weaver.backend_fingerprint(r.backend_used),
                            params=effective_params,
                        ),
                        cached_result,
                    )
                outs.append((ss, "result", r))
        return (step_index, invocation, outs)

    async def _resolve_misses(
        self,
        cap: Capability,
        invocation: CapabilityInvocation,
        entities: list[StrandSet],
        params: dict[str, Any],
    ) -> list[WeaveResult]:
        """Run the weaver across backends, applying the fallback rules.

        Returns one result per entity, aligned to ``entities``.
        ``BackendUnavailable`` retries the *whole* batch on the next backend;
        ``NO_MATCH``/``ERROR`` (per ``fallback_on``) retry only affected entities.
        ``BackendConfigurationError`` propagates and aborts the run.
        """
        results: list[WeaveResult | None] = [None] * len(entities)
        pending_idx = list(range(len(entities)))
        backends = [invocation.primary_backend, *invocation.fallback_backends]
        fallback_on = invocation.fallback_on

        for bi, backend in enumerate(backends):
            if not pending_idx:
                break
            is_last = bi == len(backends) - 1
            sub_entities = [entities[i] for i in pending_idx]
            try:
                batch_results = await self._call_batch(
                    cap, invocation, sub_entities, backend, params
                )
            except BackendConfigurationError:
                raise  # run-level: abort immediately
            except BackendUnavailable as exc:
                if FallbackCondition.BACKEND_UNAVAILABLE in fallback_on and not is_last:
                    continue  # retry the entire batch on the next backend
                for i in pending_idx:
                    results[i] = self._synth_error(
                        invocation, backend, f"BackendUnavailable: {exc}"
                    )
                pending_idx = []
                break

            next_pending: list[int] = []
            for i, r in zip(pending_idx, batch_results, strict=True):
                retryable = (
                    r.status is WeaveStatus.NO_MATCH and FallbackCondition.NO_MATCH in fallback_on
                ) or (r.status is WeaveStatus.ERROR and FallbackCondition.ERROR in fallback_on)
                if retryable and not is_last:
                    next_pending.append(i)  # only affected entities move on
                else:
                    results[i] = r
            pending_idx = next_pending

        return [r for r in results if r is not None]

    async def _call_batch(
        self,
        cap: Capability,
        invocation: CapabilityInvocation,
        entities: list[StrandSet],
        backend: str,
        params: dict[str, Any],
    ) -> list[WeaveResult]:
        """Run the step via the runner, splitting into sub-batches of max_batch_size."""
        requested = invocation.output_types
        size = cap.max_batch_size
        if size is None:
            sub_batches = [entities]
        else:
            sub_batches = [entities[i : i + size] for i in range(0, len(entities), size)]
        out: list[WeaveResult] = []
        for sb in sub_batches:
            batch = await self._runner.run_step(
                invocation.weaver_id,
                invocation.capability_id,
                backend,
                sb,
                requested,
                params=params,
            )
            validate_batch_size(
                len(sb),
                len(batch),
                context=f"{invocation.weaver_id}.{invocation.capability_id} [{backend}] runner",
            )
            out.extend(batch)
        return out

    def _apply_result(
        self,
        ss: StrandSet,
        r: WeaveResult,
        step_index: int,
        invocation: CapabilityInvocation,
        set_outputs: frozenset[str],
        remaining_steps: tuple[CapabilityInvocation, ...],
        result: ExecutionResult,
        terminal: set[str | int],
        representative: dict[str | int, WeaveResult],
        spawned: list[StrandSet],
        errored: dict[str | int, set[tuple[str, str]]],
        *,
        review_policy: ReviewPolicy,
        error_policy: ErrorPolicy,
        merge_policy: MergePolicy,
        expand_policy: ExpandPolicy,
        expand_by_type: dict[str, ExpandPolicy],
        confidence_threshold: float,
        expansion_budget: _ExpansionBudget,
    ) -> None:
        """Fold one step's result into an entity and record its completion outcome.

        NO_MATCH and ERROR are both *branch-local*: each is recorded and the entity keeps
        going, so a failed branch (e.g. one DB that 5xx'd) never discards the data its
        sibling branches already produced. An ERROR additionally classifies the failure
        and notes the failed node so a fully-blocked entity can be rerouted; only
        ``ErrorPolicy.RAISE`` makes it abort. AMBIGUOUS pauses under HALT; an explicit
        ALLOW_CONTINUE permits TOP selection or TOP_K/ALL expansion, subject to the
        confidence floor. OK + review is entity-terminal under HALT.
        """
        cap_id = invocation.capability_id

        if r.status is WeaveStatus.NO_MATCH:
            ss.completion.append(StepOutcome(cap_id, r.backend_used, "no_match"))
            representative.setdefault(entity_key(ss), r)
            return

        if r.status is WeaveStatus.ERROR:
            if error_policy is ErrorPolicy.RAISE:
                raise BraidworksError(
                    f"weaver ERROR at step {step_index} ({cap_id}): "
                    f"{'; '.join(r.errors) or 'unspecified'}"
                )
            message = "; ".join(r.errors) or "weaver returned ERROR"
            result.errors.append(
                ExecutionError(
                    strand_set=ss,
                    error_type="WeaverError",
                    message=message,
                    step_index=step_index,
                    capability_id=cap_id,
                    category=classify_error(message),
                )
            )
            ss.completion.append(StepOutcome(cap_id, r.backend_used, "error"))
            # Branch-local: record the failed node and keep the entity live so its other
            # branches still run; a fully-blocked entity is rerouted after the chunk.
            errored.setdefault(entity_key(ss), set()).add((invocation.weaver_id, cap_id))
            return

        if r.status is WeaveStatus.AMBIGUOUS:
            if review_policy is ReviewPolicy.RAISE:
                raise ReviewRequired(f"ambiguous result at step {step_index} ({cap_id})")
            if review_policy is ReviewPolicy.HALT:
                result.review_queue.append(ReviewQueueItem(ss, r, remaining_steps))
                terminal.add(entity_key(ss))
                return
            # Cardinality fan-out: when the result carries candidates, ``ExpandPolicy``
            # decides how many successors continue — TOP collapses to the best one,
            # TOP_K/ALL fork the entity into independent children. With no candidates
            # there is nothing to pick or fork, so fall back to today's review/raise.
            if r.candidates:
                selected = _rank_candidates(r.candidates)[
                    : expand_policy.fork_count(len(r.candidates))
                ]
                below_threshold = confidence_threshold > 0 and any(
                    candidate.confidence < confidence_threshold
                    or any(strand.confidence < confidence_threshold for strand in candidate.strands)
                    for candidate in selected
                )
                if below_threshold:
                    result.review_queue.append(ReviewQueueItem(ss, r, remaining_steps))
                    terminal.add(entity_key(ss))
                    return
                # Auto-selection must not erase that the source was ambiguous.
                ss.requires_review = True
                ss.warnings.extend(r.warnings)
                ss.errors.extend(r.errors)
                self._expand_candidates(
                    ss,
                    r,
                    cap_id,
                    spawned,
                    terminal,
                    expand_policy,
                    merge_policy,
                    expansion_budget,
                    result,
                )
                return
            result.review_queue.append(ReviewQueueItem(ss, r, remaining_steps))
            terminal.add(entity_key(ss))
            return

        # status is OK.
        below_threshold = self._below_threshold(r, confidence_threshold)
        needs_review = r.requires_review or below_threshold
        if needs_review:
            if review_policy is ReviewPolicy.RAISE:
                raise ReviewRequired(f"result requires review at step {step_index} ({cap_id})")
            if review_policy is ReviewPolicy.HALT or below_threshold:
                result.review_queue.append(ReviewQueueItem(ss, r, remaining_steps))
                terminal.add(entity_key(ss))
                return
            # ReviewPolicy.ALLOW_CONTINUE falls through to merge and continue.

        ss.merge_result(r, merge_policy)
        ss.completion.append(
            StepOutcome(cap_id, r.backend_used, "ok", tuple(s.type_id for s in r.strands))
        )
        # A produced set-output strand is the authoritative fan dimension, so it must win
        # over any pre-existing value of that type — notably when a capability *consumes
        # and produces the same key* (e.g. taxid -> child taxids), where the input scalar
        # would otherwise shadow the produced list under HIGHEST_CONFIDENCE. Re-apply the
        # produced set-output strands LAST_WINS before expanding.
        if set_outputs:
            for s in r.strands:
                if s.type_id in set_outputs:
                    ss.add_strand(s, MergePolicy.LAST_WINS)
        # Mid-braid cardinality fan-out: if this step produced any set-valued join key,
        # ExpandPolicy decides whether the entity continues as one (TOP) or forks into
        # one child per value (TOP_K/ALL) so the braid drills each.
        if set_outputs:
            self._expand_set_outputs(
                ss,
                set_outputs,
                cap_id,
                spawned,
                terminal,
                expand_policy,
                expand_by_type,
                merge_policy,
                expansion_budget,
                result,
            )

    def _expand_candidates(
        self,
        ss: StrandSet,
        r: WeaveResult,
        cap_id: str,
        spawned: list[StrandSet],
        terminal: set[str | int],
        expand_policy: ExpandPolicy,
        merge_policy: MergePolicy,
        expansion_budget: _ExpansionBudget,
        result: ExecutionResult,
    ) -> None:
        """Resolve an AMBIGUOUS result's candidates per ``expand_policy``.

        ``TOP`` merges the single best candidate into ``ss`` in place (it stays live).
        ``TOP_K``/``ALL`` replace ``ss`` with N lineage-tagged children, each carrying
        the parent strands plus one candidate's strands, appended to ``spawned``.
        """
        ranked = _rank_candidates(r.candidates)
        n = len(ranked)

        if expand_policy.mode is ExpandMode.TOP:
            best = ranked[0]
            for strand in best.strands:
                ss.add_strand(strand, merge_policy)
            ss.completion.append(
                StepOutcome(cap_id, r.backend_used, "ok", tuple(s.type_id for s in best.strands))
            )
            if n > 1:
                # Not a silent collapse: record that N-1 alternatives were discarded.
                ss.warnings.append(
                    f"ExpandPolicy.TOP: auto-selected 1 of {n} candidates at {cap_id}"
                )
            return

        # TOP_K / ALL: fork. The originating-input id is preserved across forks so
        # leaves regroup to the original query even if a later step forks again.
        root = ss.parent_id if ss.parent_id is not None else ss.entity_id
        take = expand_policy.fork_count(n)
        take = expansion_budget.reserve(take, ss, cap_id, result)
        for i, cand in enumerate(ranked[:take]):
            child = ss.clone(entity_id=f"{ss.entity_id}#{i}", parent_id=root)
            for strand in cand.strands:
                child.add_strand(strand, merge_policy)
            child.completion.append(
                StepOutcome(cap_id, r.backend_used, "ok", tuple(s.type_id for s in cand.strands))
            )
            expansion_budget.identify(child)
            spawned.append(child)
        if take < n:
            logger.warning(
                "ExpandPolicy.%s: kept %d of %d candidates at %s",
                expand_policy.mode.name,
                take,
                n,
                cap_id,
            )
        terminal.add(entity_key(ss))  # the parent is replaced by its children

    def _expand_set_outputs(
        self,
        ss: StrandSet,
        set_outputs: frozenset[str],
        cap_id: str,
        spawned: list[StrandSet],
        terminal: set[str | int],
        expand_policy: ExpandPolicy,
        expand_by_type: dict[str, ExpandPolicy],
        merge_policy: MergePolicy,
        expansion_budget: _ExpansionBudget,
        result: ExecutionResult,
    ) -> None:
        """Fork ``ss`` on each set-valued produced join key, per its ``ExpandPolicy``.

        A set output's strand carries a *list* of values. ``TOP``/``TOP_K(1)`` collapse
        that list to one representative in place (the entity stays live); ``TOP_K(k>1)``
        / ``ALL`` replace the entity with children — the **cross-product** across every
        forking dimension — each holding one scalar value so the braid drills it. Reuses
        the Phase-1 lineage scheme (``entity_id`` ``parent#i``, ``parent_id`` = root).
        """
        # Gather the fan dimensions actually present on this entity, with their policy.
        dims: list[tuple[str, list, ExpandPolicy, Strand]] = []
        for type_id in sorted(set_outputs):
            strand = ss.get(type_id)
            if strand is None or strand.value is None:
                continue
            raw = strand.value if isinstance(strand.value, list) else [strand.value]
            seen: set[str] = set()
            values: list = []
            for v in raw:  # de-dup, preserve the weaver's best-first order
                key = json.dumps(v, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    values.append(v)
            if values:
                dims.append((type_id, values, expand_by_type.get(type_id, expand_policy), strand))
        if not dims:
            return

        root = ss.parent_id if ss.parent_id is not None else ss.entity_id
        forks: list[tuple[str, list, Strand]] = []
        for type_id, values, policy, strand in dims:
            take = policy.fork_count(len(values))
            if take == 1:
                ss.add_strand(
                    Strand(
                        type_id,
                        values[0],
                        confidence=strand.confidence,
                        provenance=strand.provenance,
                        metadata=dict(strand.metadata),
                    ),
                    MergePolicy.LAST_WINS,
                )
                if len(values) > 1:
                    ss.warnings.append(
                        f"ExpandPolicy.{policy.mode.name}: auto-selected 1 of "
                        f"{len(values)} {type_id} at {cap_id}"
                    )
            else:
                forks.append((type_id, values[:take], strand))
                if take < len(values):
                    ss.warnings.append(
                        f"ExpandPolicy.{policy.mode.name}: kept {take} of "
                        f"{len(values)} {type_id} at {cap_id}"
                    )
        if not forks:
            return

        requested = prod(len(values) for _, values, _ in forks)
        take = expansion_budget.reserve(requested, ss, cap_id, result)
        # Enumerate only retained combinations, cloning once per final child.
        # Dimension order and nested IDs match the previous cross-product order.
        combinations = product(*(range(len(values)) for _, values, _ in forks))
        for indices in islice(combinations, take):
            suffix = "".join(f"#{index}" for index in indices)
            child = ss.clone(entity_id=ss.entity_id + suffix, parent_id=root)
            for (type_id, values, strand), index in zip(forks, indices, strict=True):
                child.add_strand(
                    Strand(
                        type_id,
                        values[index],
                        confidence=strand.confidence,
                        provenance=strand.provenance,
                        metadata=dict(strand.metadata),
                    ),
                    MergePolicy.LAST_WINS,
                )
            expansion_budget.identify(child)
            spawned.append(child)
        terminal.add(entity_key(ss))

    @staticmethod
    def _below_threshold(r: WeaveResult, threshold: float) -> bool:
        if threshold <= 0.0:
            return False  # disabled
        return any(s.confidence < threshold for s in r.strands)

    @staticmethod
    def _synth_no_match(braid: Braid) -> WeaveResult:
        """A placeholder NO_MATCH for an entity that produced no target on any branch."""
        cap_id = braid.steps[0].capability_id if braid.steps else ""
        return WeaveResult(
            capability_id=cap_id,
            weaver_version="",
            backend_used="",
            computed_groups=frozenset(),
            status=WeaveStatus.NO_MATCH,
        )

    @staticmethod
    def _synth_error(invocation: CapabilityInvocation, backend: str, message: str) -> WeaveResult:
        return WeaveResult(
            capability_id=invocation.capability_id,
            weaver_version="",
            backend_used=backend,
            computed_groups=frozenset(),
            status=WeaveStatus.ERROR,
            errors=(message,),
        )


def _candidate_sort_key(c: CandidateResult) -> tuple[float, str]:
    """Deterministic ordering: highest confidence first, ties broken by a stable
    serialization of the candidate's strands so fan-out is reproducible run to run."""
    strand_repr = json.dumps(
        sorted((s.type_id, s.value) for s in c.strands),
        sort_keys=True,
        default=str,
    )
    return (-c.confidence, strand_repr)


def _rank_candidates(candidates: tuple[CandidateResult, ...]) -> list[CandidateResult]:
    return sorted(candidates, key=_candidate_sort_key)


def _flag_recovered(result: ExecutionResult, ss: StrandSet) -> None:
    """Mark every recorded error of entity ``ss`` as recovered (a reroute reached the
    targets another way), so it reports as a warning rather than a fatal failure."""
    for e in result.errors:
        if e.strand_set is ss:
            e.recovered = True
