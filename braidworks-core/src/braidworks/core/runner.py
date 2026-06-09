"""WeaveStepRunner — the one seam where a weave-step's execution is pluggable.

A *weave-step* is the atomic unit of work the executor dispatches: run one
capability, on one concrete backend, over a batch of ``StrandSet``s, asking for a
fixed set of outputs. It is a pure function of those inputs plus the backend's
fingerprint (which is why ``compute_cache_key`` can key it), so it is exactly the
thing that can be moved off-process onto a queue.

``LocalExecutor`` owns all the *orchestration* around a step — cache split, backend
fallback, classification, review queue, merge, chunking — and that stays in-process.
It calls a :class:`WeaveStepRunner` only for the step itself. The default
:class:`InProcessStepRunner` just calls ``weaver.execute_batch`` (the historical
behavior); a distributed runner (e.g. a Celery-backed one in ``braidworks-celery``)
submits the step to a worker and awaits the result, without the executor changing.

This is the deliberate, transport-neutral boundary: core declares the interface and
ships the in-process implementation; no broker dependency leaks into core.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from braidworks.core.registry import BraidRegistry
    from braidworks.core.result import WeaveResult
    from braidworks.core.strand import StrandSet


@runtime_checkable
class WeaveStepRunner(Protocol):
    """Runs a single weave-step batch and returns one result per input, in order.

    Implementations must preserve the ``execute_batch`` contract: exactly one
    ``WeaveResult`` per input ``StrandSet``, aligned to input order. ``backend`` is
    always a single concrete backend (fallback is the executor's job, not the
    runner's). The call may run in-process or be dispatched to a worker; either way
    it is awaited.
    """

    async def run_step(
        self,
        weaver_id: str,
        capability_id: str,
        backend: str,
        strand_sets: list[StrandSet],
        requested_outputs: frozenset[str],
    ) -> list[WeaveResult]: ...


class InProcessStepRunner:
    """Default runner: resolve the weaver from the registry and call it directly.

    This is the behavior braidworks has always had — the step runs in the same
    process and event loop as the executor. It exists as an explicit object so the
    executor depends on the :class:`WeaveStepRunner` interface rather than on a bare
    ``weaver.execute_batch`` call, leaving room for an off-process runner.
    """

    def __init__(self, registry: BraidRegistry) -> None:
        self._registry = registry

    async def run_step(
        self,
        weaver_id: str,
        capability_id: str,
        backend: str,
        strand_sets: list[StrandSet],
        requested_outputs: frozenset[str],
    ) -> list[WeaveResult]:
        weaver = self._registry.get_weaver(weaver_id)
        return await weaver.execute_batch(
            capability_id,
            strand_sets,
            requested_outputs=requested_outputs,
            backend=backend,
        )
