"""CeleryStepRunner — the WeaveStepRunner the executor calls to dispatch a step.

It serializes the batch, submits a ``weave_step`` task to the weaver's dedicated
queue, and awaits the result. Both the submit and the blocking ``.get()`` run in a
worker thread (``asyncio.to_thread``) for two reasons: it keeps the executor's event
loop free while the step is in flight, and — crucially — it means the task body runs
*off* the running loop, so its ``asyncio.run`` works even in Celery's eager (test)
mode where ``apply_async`` executes inline.
"""

from __future__ import annotations

import asyncio

from braidworks.core.result import WeaveResult
from braidworks.core.strand import StrandSet

from braidworks_celery.app import queue_for
from braidworks_celery.tasks import weave_step


class CeleryStepRunner:
    """A ``WeaveStepRunner`` that dispatches each step to a Celery worker.

    ``result_timeout`` bounds how long the orchestrator waits for one step's batch
    before raising (a stuck worker must not wedge the whole run forever).
    """

    def __init__(self, *, result_timeout: float | None = 300.0) -> None:
        self._result_timeout = result_timeout

    async def run_step(
        self,
        weaver_id: str,
        capability_id: str,
        backend: str,
        strand_sets: list[StrandSet],
        requested_outputs: frozenset[str],
    ) -> list[WeaveResult]:
        payload = [ss.to_json() for ss in strand_sets]
        requested = list(requested_outputs)
        results_json = await asyncio.to_thread(
            self._submit_and_wait, weaver_id, capability_id, backend, payload, requested
        )
        return [WeaveResult.from_json(r) for r in results_json]

    def _submit_and_wait(
        self,
        weaver_id: str,
        capability_id: str,
        backend: str,
        payload: list[dict],
        requested: list[str],
    ) -> list[dict]:
        async_result = weave_step.apply_async(
            args=[weaver_id, capability_id, backend, payload, requested],
            queue=queue_for(weaver_id),
        )
        return async_result.get(timeout=self._result_timeout)
