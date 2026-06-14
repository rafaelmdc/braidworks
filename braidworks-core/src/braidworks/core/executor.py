"""Executor data structures, policies, and the in-process LocalExecutor."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from braidworks.core.braid import Braid, CapabilityInvocation, FallbackCondition
from braidworks.core.cache import StrandCache, compute_cache_key
from braidworks.core.capability import Capability
from braidworks.core.exceptions import (
    BackendConfigurationError,
    BackendUnavailable,
    BraidworksError,
    ReviewRequired,
)
from braidworks.core.references import Reference, references_for_braid
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import CandidateResult, WeaveResult, WeaveStatus
from braidworks.core.runner import InProcessStepRunner, WeaveStepRunner
from braidworks.core.strand import MergePolicy, StepOutcome, StrandSet

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


class ReviewPolicy(Enum):
    """What the executor does on ``OK + requires_review`` or a low-confidence result.

    ``AMBIGUOUS`` always halts or raises regardless of this — ``ALLOW_CONTINUE``
    never applies to it (there are no strands to merge).
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

    def to_json(self) -> dict[str, Any]:
        return {
            "strand_set": self.strand_set.to_json(),
            "triggering_result": self.triggering_result.to_json(),
            "remaining_steps": [s.to_json() for s in self.remaining_steps],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ReviewQueueItem:
        return cls(
            strand_set=StrandSet.from_json(data["strand_set"]),
            triggering_result=WeaveResult.from_json(data["triggering_result"]),
            remaining_steps=tuple(
                CapabilityInvocation.from_json(s) for s in data["remaining_steps"]
            ),
        )


@dataclass
class ExecutionError:
    """A structural/technical failure captured without a raw Exception object."""

    strand_set: StrandSet
    error_type: str
    message: str
    step_index: int | None = None  # None = preflight failure
    capability_id: str | None = None  # None = preflight failure

    def to_json(self) -> dict[str, Any]:
        return {
            "strand_set": self.strand_set.to_json(),
            "error_type": self.error_type,
            "message": self.message,
            "step_index": self.step_index,
            "capability_id": self.capability_id,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ExecutionError:
        return cls(
            strand_set=StrandSet.from_json(data["strand_set"]),
            error_type=data["error_type"],
            message=data["message"],
            step_index=data.get("step_index"),
            capability_id=data.get("capability_id"),
        )


@dataclass
class ExecutionResult:
    """The four mutually exclusive, exhaustive outcome buckets for a batch."""

    resolved: list[StrandSet] = field(default_factory=list)
    unresolved: list[tuple[StrandSet, WeaveResult]] = field(default_factory=list)
    review_queue: list[ReviewQueueItem] = field(default_factory=list)
    errors: list[ExecutionError] = field(default_factory=list)
    # Citations for the sources this run drew on, ordered by weaver_id (issue #1).
    # Derived from the executed braid's weavers; empty when none carry provenance.
    references: list[Reference] = field(default_factory=list)

    def total(self) -> int:
        return (
            len(self.resolved)
            + len(self.unresolved)
            + len(self.review_queue)
            + len(self.errors)
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "resolved": [ss.to_json() for ss in self.resolved],
            "unresolved": [
                [ss.to_json(), wr.to_json()] for ss, wr in self.unresolved
            ],
            "review_queue": [item.to_json() for item in self.review_queue],
            "errors": [e.to_json() for e in self.errors],
            "references": [r.to_json() for r in self.references],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ExecutionResult:
        return cls(
            resolved=[StrandSet.from_json(ss) for ss in data.get("resolved", [])],
            unresolved=[
                (StrandSet.from_json(ss), WeaveResult.from_json(wr))
                for ss, wr in data.get("unresolved", [])
            ],
            review_queue=[
                ReviewQueueItem.from_json(item) for item in data.get("review_queue", [])
            ],
            errors=[ExecutionError.from_json(e) for e in data.get("errors", [])],
            references=[Reference.from_json(r) for r in data.get("references", [])],
        )


class LocalExecutor:
    """Runs a Braid against a list of StrandSets in-process with asyncio.

    Every input entity lands in exactly one bucket of the returned
    ``ExecutionResult`` (resolved / unresolved / review_queue / errors), unless a
    RAISE policy or ``BackendConfigurationError`` aborts the whole run.
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
        expand_policy: ExpandPolicy = ExpandPolicy(),
        confidence_threshold: float = 0.0,
        chunk_size: int = 10_000,
        max_expansion: int = 10_000,
    ) -> ExecutionResult:
        result = ExecutionResult()
        # Citations for every source this braid draws on (issue #1). Computed from the
        # plan up front so the result carries its references regardless of outcome.
        result.references = list(references_for_braid(braid, self._registry))

        # Preflight (once): entities missing the braid's starting types fail here.
        survivors: list[StrandSet] = []
        for ss in strand_sets:
            missing = braid.from_types - ss.available_types()
            if missing:
                result.errors.append(
                    ExecutionError(
                        strand_set=ss,
                        error_type="MissingInputError",
                        message=f"missing required input types: {sorted(missing)}",
                        step_index=None,
                        capability_id=None,
                    )
                )
            else:
                survivors.append(ss)

        # Chunked processing: each chunk runs through all steps before the next.
        for start in range(0, len(survivors), chunk_size):
            chunk = survivors[start : start + chunk_size]
            await self._run_chunk(
                braid,
                chunk,
                result,
                review_policy=review_policy,
                error_policy=error_policy,
                merge_policy=merge_policy,
                expand_policy=expand_policy,
                confidence_threshold=confidence_threshold,
                max_expansion=max_expansion,
            )
        return result

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
        confidence_threshold: float,
        max_expansion: int,
    ) -> None:
        live = list(chunk)  # entities still progressing (not terminally bucketed)
        terminal: set[int] = set()  # id(entity) already placed in errors/review_queue
        representative: dict[int, WeaveResult] = {}  # a NO_MATCH to attach if unresolved
        waves = braid.waves()

        for wi, wave in enumerate(waves):
            if not live:
                break
            # Children spawned by fan-out this wave; folded into ``live`` afterwards so
            # they flow through the remaining waves alongside un-forked entities.
            spawned: list[StrandSet] = []
            # Steps in a wave are independent → run them concurrently. Each job only
            # awaits I/O and never mutates an entity, so results are merged afterwards
            # in deterministic step order (no shared-state hazard across the gather).
            jobs = [self._run_step_over(braid, si, live) for si in wave]
            wave_results = await asyncio.gather(*jobs)
            remaining_steps = tuple(
                braid.steps[si] for later in waves[wi + 1 :] for si in later
            )

            for step_index, invocation, outs in sorted(wave_results, key=lambda t: t[0]):
                for ss, kind, payload in outs:
                    if id(ss) in terminal:
                        continue
                    if kind == "skipped":
                        ss.completion.append(
                            StepOutcome(invocation.capability_id, "", "skipped")
                        )
                        continue
                    if kind == "satisfied":
                        produced = tuple(
                            sorted(invocation.output_types & ss.available_types())
                        )
                        ss.completion.append(
                            StepOutcome(invocation.capability_id, "", "ok", produced)
                        )
                        continue
                    self._apply_result(
                        ss,
                        payload,
                        step_index,
                        invocation,
                        remaining_steps,
                        result,
                        terminal,
                        representative,
                        spawned,
                        review_policy=review_policy,
                        error_policy=error_policy,
                        merge_policy=merge_policy,
                        expand_policy=expand_policy,
                        confidence_threshold=confidence_threshold,
                    )

            if terminal:
                live = [ss for ss in live if id(ss) not in terminal]
            if spawned:
                room = max_expansion - len(live)
                if room < len(spawned):
                    logger.warning(
                        "fan-out cap %d reached: dropping %d of %d expanded entities",
                        max_expansion,
                        len(spawned) - max(room, 0),
                        len(spawned),
                    )
                    spawned = spawned[: max(room, 0)]
                live.extend(spawned)

        # Survivors: resolved if any requested target type was produced (branches are
        # best-effort enrichment — empty branches are recorded in completion, not a
        # failure), else unresolved.
        for ss in live:
            if braid.to_types & ss.available_types():
                result.resolved.append(ss)
            else:
                rep = representative.get(id(ss)) or self._synth_no_match(braid)
                result.unresolved.append((ss, rep))

    async def _run_step_over(
        self, braid: Braid, step_index: int, entities: list[StrandSet]
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
            )
            cached = self._cache.get(key, triggered)
            if cached is not None:
                outs.append((ss, "result", cached))
            else:
                misses.append(ss)

        if misses:
            miss_results = await self._resolve_misses(cap, invocation, misses)
            for ss, r in zip(misses, miss_results):
                if r.status is not WeaveStatus.ERROR:
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
                        ),
                        r,
                    )
                outs.append((ss, "result", r))
        return (step_index, invocation, outs)

    async def _resolve_misses(
        self,
        cap: Capability,
        invocation: CapabilityInvocation,
        entities: list[StrandSet],
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
                    cap, invocation, sub_entities, backend
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
            for i, r in zip(pending_idx, batch_results):
                retryable = (
                    r.status is WeaveStatus.NO_MATCH
                    and FallbackCondition.NO_MATCH in fallback_on
                ) or (
                    r.status is WeaveStatus.ERROR
                    and FallbackCondition.ERROR in fallback_on
                )
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
            out.extend(
                await self._runner.run_step(
                    invocation.weaver_id,
                    invocation.capability_id,
                    backend,
                    sb,
                    requested,
                )
            )
        return out

    def _apply_result(
        self,
        ss: StrandSet,
        r: WeaveResult,
        step_index: int,
        invocation: CapabilityInvocation,
        remaining_steps: tuple[CapabilityInvocation, ...],
        result: ExecutionResult,
        terminal: set[int],
        representative: dict[int, WeaveResult],
        spawned: list[StrandSet],
        *,
        review_policy: ReviewPolicy,
        error_policy: ErrorPolicy,
        merge_policy: MergePolicy,
        expand_policy: ExpandPolicy,
        confidence_threshold: float,
    ) -> None:
        """Fold one step's result into an entity and record its completion outcome.

        NO_MATCH is *branch-local*: it is recorded and the entity keeps going (another
        branch or a later wave may still produce a target). ERROR is entity-terminal.
        AMBIGUOUS is governed by ``expand_policy``: with candidates it collapses
        (``TOP``) or forks into children (``TOP_K``/``ALL``); with no candidates it
        falls back to the review/raise path. OK + review is entity-terminal under HALT.
        """
        cap_id = invocation.capability_id

        if r.status is WeaveStatus.NO_MATCH:
            ss.completion.append(StepOutcome(cap_id, r.backend_used, "no_match"))
            representative.setdefault(id(ss), r)
            return

        if r.status is WeaveStatus.ERROR:
            if error_policy is ErrorPolicy.RAISE:
                raise BraidworksError(
                    f"weaver ERROR at step {step_index} ({cap_id}): "
                    f"{'; '.join(r.errors) or 'unspecified'}"
                )
            result.errors.append(
                ExecutionError(
                    strand_set=ss,
                    error_type="WeaverError",
                    message="; ".join(r.errors) or "weaver returned ERROR",
                    step_index=step_index,
                    capability_id=cap_id,
                )
            )
            terminal.add(id(ss))
            return

        if r.status is WeaveStatus.AMBIGUOUS:
            # Cardinality fan-out: when the result carries candidates, ``ExpandPolicy``
            # decides how many successors continue — TOP collapses to the best one,
            # TOP_K/ALL fork the entity into independent children. With no candidates
            # there is nothing to pick or fork, so fall back to today's review/raise.
            if r.candidates:
                self._expand_candidates(
                    ss, r, cap_id, spawned, terminal, expand_policy, merge_policy
                )
                return
            if review_policy is ReviewPolicy.RAISE:
                raise ReviewRequired(f"ambiguous result at step {step_index} ({cap_id})")
            result.review_queue.append(ReviewQueueItem(ss, r, remaining_steps))
            terminal.add(id(ss))
            return

        # status is OK.
        needs_review = r.requires_review or self._below_threshold(r, confidence_threshold)
        if needs_review:
            if review_policy is ReviewPolicy.RAISE:
                raise ReviewRequired(
                    f"result requires review at step {step_index} ({cap_id})"
                )
            if review_policy is ReviewPolicy.HALT:
                result.review_queue.append(ReviewQueueItem(ss, r, remaining_steps))
                terminal.add(id(ss))
                return
            # ReviewPolicy.ALLOW_CONTINUE falls through to merge and continue.

        ss.merge_result(r, merge_policy)
        ss.completion.append(
            StepOutcome(cap_id, r.backend_used, "ok", tuple(s.type_id for s in r.strands))
        )

    def _expand_candidates(
        self,
        ss: StrandSet,
        r: WeaveResult,
        cap_id: str,
        spawned: list[StrandSet],
        terminal: set[int],
        expand_policy: ExpandPolicy,
        merge_policy: MergePolicy,
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
                StepOutcome(
                    cap_id, r.backend_used, "ok", tuple(s.type_id for s in best.strands)
                )
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
        for i, cand in enumerate(ranked[:take]):
            child = ss.clone(entity_id=f"{ss.entity_id}#{i}", parent_id=root)
            for strand in cand.strands:
                child.add_strand(strand, merge_policy)
            child.completion.append(
                StepOutcome(
                    cap_id, r.backend_used, "ok", tuple(s.type_id for s in cand.strands)
                )
            )
            spawned.append(child)
        if take < n:
            logger.warning(
                "ExpandPolicy.%s: kept %d of %d candidates at %s",
                expand_policy.mode.name,
                take,
                n,
                cap_id,
            )
        terminal.add(id(ss))  # the parent is replaced by its children

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
    def _synth_error(
        invocation: CapabilityInvocation, backend: str, message: str
    ) -> WeaveResult:
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
