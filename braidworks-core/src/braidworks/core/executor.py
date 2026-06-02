"""Executor data structures, policies, and the in-process LocalExecutor."""

from __future__ import annotations

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
    MissingInputError,
    ReviewRequired,
)
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import MergePolicy, StrandSet
from braidworks.core.weaver import BaseWeaver


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
        )


class LocalExecutor:
    """Runs a Braid against a list of StrandSets in-process with asyncio.

    Every input entity lands in exactly one bucket of the returned
    ``ExecutionResult`` (resolved / unresolved / review_queue / errors), unless a
    RAISE policy or ``BackendConfigurationError`` aborts the whole run.
    """

    def __init__(self, registry: BraidRegistry, cache: StrandCache | None = None) -> None:
        from braidworks.core.cache import InMemoryStrandCache

        self._registry = registry
        self._cache: StrandCache = cache if cache is not None else InMemoryStrandCache()

    async def execute(
        self,
        braid: Braid,
        strand_sets: list[StrandSet],
        *,
        review_policy: ReviewPolicy = ReviewPolicy.HALT,
        error_policy: ErrorPolicy = ErrorPolicy.RECORD_AND_CONTINUE,
        merge_policy: MergePolicy = MergePolicy.HIGHEST_CONFIDENCE,
        confidence_threshold: float = 0.0,
        chunk_size: int = 10_000,
    ) -> ExecutionResult:
        result = ExecutionResult()

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
                confidence_threshold=confidence_threshold,
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
        confidence_threshold: float,
    ) -> None:
        active = list(chunk)
        for step_index, invocation in enumerate(braid.steps):
            if not active:
                break
            weaver = self._registry.get_weaver(invocation.weaver_id)
            cap = self._registry.get_capability(invocation.weaver_id, invocation.capability_id)
            requested = invocation.output_types
            triggered = cap.triggered_groups(requested)
            dataset_version = weaver.dataset_version()
            manifest_version = weaver.MANIFEST.version
            remaining_steps = braid.steps[step_index + 1 :]

            next_active: list[StrandSet] = []
            pending: list[tuple[StrandSet, WeaveResult]] = []  # (entity, result) to classify
            misses: list[StrandSet] = []

            # Guard 1 + cache split.
            for ss in active:
                if requested <= ss.available_types():
                    next_active.append(ss)  # already satisfied; no call, no lookup
                    continue
                key = compute_cache_key(
                    cap,
                    ss,
                    capability_version=manifest_version,
                    backend=invocation.primary_backend,
                    dataset_version=dataset_version,
                )
                cached = self._cache.get(key, triggered)
                if cached is not None:
                    pending.append((ss, cached))
                else:
                    misses.append(ss)

            # Resolve misses (with backend fallback), cache them, queue for classify.
            if misses:
                miss_results = await self._resolve_misses(weaver, cap, invocation, misses)
                for ss, r in zip(misses, miss_results):
                    if r.status is not WeaveStatus.ERROR:
                        # Cache every non-error result, including NO_MATCH and AMBIGUOUS,
                        # so a second pass is a hit. Key by the backend that produced it.
                        self._cache.put(
                            compute_cache_key(
                                cap,
                                ss,
                                capability_version=r.capability_version,
                                backend=r.backend_used,
                                dataset_version=dataset_version,
                            ),
                            r,
                        )
                    pending.append((ss, r))

            # Classify hits and misses identically (cache hits get no special path).
            for ss, r in pending:
                keep = self._classify(
                    ss,
                    r,
                    step_index,
                    invocation,
                    remaining_steps,
                    result,
                    review_policy=review_policy,
                    error_policy=error_policy,
                    merge_policy=merge_policy,
                    confidence_threshold=confidence_threshold,
                )
                if keep:
                    next_active.append(ss)

            active = next_active

        # Entities that survived every step are resolved.
        result.resolved.extend(active)

    async def _resolve_misses(
        self,
        weaver: BaseWeaver,
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
                    weaver, cap, invocation, sub_entities, backend
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
        weaver: BaseWeaver,
        cap: Capability,
        invocation: CapabilityInvocation,
        entities: list[StrandSet],
        backend: str,
    ) -> list[WeaveResult]:
        """Call execute_batch, splitting into sub-batches of at most max_batch_size."""
        requested = invocation.output_types
        size = cap.max_batch_size
        if size is None:
            sub_batches = [entities]
        else:
            sub_batches = [entities[i : i + size] for i in range(0, len(entities), size)]
        out: list[WeaveResult] = []
        for sb in sub_batches:
            out.extend(
                await weaver.execute_batch(
                    invocation.capability_id,
                    sb,
                    requested_outputs=requested,
                    backend=backend,
                )
            )
        return out

    def _classify(
        self,
        ss: StrandSet,
        r: WeaveResult,
        step_index: int,
        invocation: CapabilityInvocation,
        remaining_steps: tuple[CapabilityInvocation, ...],
        result: ExecutionResult,
        *,
        review_policy: ReviewPolicy,
        error_policy: ErrorPolicy,
        merge_policy: MergePolicy,
        confidence_threshold: float,
    ) -> bool:
        """Route one result. Returns True if the entity stays active, else it has
        been placed in a terminal bucket (or an exception is raised)."""
        if r.status is WeaveStatus.NO_MATCH:
            result.unresolved.append((ss, r))
            return False

        if r.status is WeaveStatus.ERROR:
            if error_policy is ErrorPolicy.RAISE:
                raise BraidworksError(
                    f"weaver ERROR at step {step_index} ({invocation.capability_id}): "
                    f"{'; '.join(r.errors) or 'unspecified'}"
                )
            result.errors.append(
                ExecutionError(
                    strand_set=ss,
                    error_type="WeaverError",
                    message="; ".join(r.errors) or "weaver returned ERROR",
                    step_index=step_index,
                    capability_id=invocation.capability_id,
                )
            )
            return False

        if r.status is WeaveStatus.AMBIGUOUS:
            # AMBIGUOUS always halts or raises; ALLOW_CONTINUE never applies.
            if review_policy is ReviewPolicy.RAISE:
                raise ReviewRequired(
                    f"ambiguous result at step {step_index} ({invocation.capability_id})"
                )
            result.review_queue.append(ReviewQueueItem(ss, r, remaining_steps))
            return False

        # status is OK.
        needs_review = r.requires_review or self._below_threshold(r, confidence_threshold)
        if needs_review:
            if review_policy is ReviewPolicy.RAISE:
                raise ReviewRequired(
                    f"result requires review at step {step_index} "
                    f"({invocation.capability_id})"
                )
            if review_policy is ReviewPolicy.HALT:
                result.review_queue.append(ReviewQueueItem(ss, r, remaining_steps))
                return False
            # ReviewPolicy.ALLOW_CONTINUE falls through to merge and continue.

        ss.merge_result(r, merge_policy)
        return True

    @staticmethod
    def _below_threshold(r: WeaveResult, threshold: float) -> bool:
        if threshold <= 0.0:
            return False  # disabled
        return any(s.confidence < threshold for s in r.strands)

    @staticmethod
    def _synth_error(
        invocation: CapabilityInvocation, backend: str, message: str
    ) -> WeaveResult:
        return WeaveResult(
            capability_id=invocation.capability_id,
            capability_version="",
            backend_used=backend,
            computed_groups=frozenset(),
            status=WeaveStatus.ERROR,
            errors=(message,),
        )
