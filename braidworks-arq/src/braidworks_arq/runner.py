"""ArqStepRunner — the WeaveStepRunner the executor calls to dispatch a step.

Because arq is async-native, this is the clean version of the seam: serialize the
batch, ``await`` an enqueue on the weaver's queue, ``await`` the job result. No
worker thread, no ``asyncio.run``, no result-join guard — the orchestrator's event
loop stays free while the step is in flight on a worker.
"""

from __future__ import annotations

from typing import Any

from arq import create_pool
from arq.connections import ArqRedis

from braidworks.core.result import WeaveResult
from braidworks.core.strand import StrandSet

from braidworks_arq.settings import queue_for, redis_settings
from braidworks_arq.tasks import weave_step

_FUNCTION_NAME = weave_step.__name__


class ArqStepRunner:
    """A ``WeaveStepRunner`` that dispatches each step to an arq worker over Redis.

    A connection pool is created lazily on first use and reused. ``result_timeout``
    bounds how long the orchestrator waits for one step's batch before raising (a
    stuck worker must not wedge the whole run forever). ``pool`` may be injected (the
    test suite passes an inline pool so the suite needs no Redis).
    """

    def __init__(self, *, pool: Any | None = None, result_timeout: float | None = 300.0) -> None:
        self._pool = pool
        self._result_timeout = result_timeout

    async def _get_pool(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(redis_settings())
        return self._pool

    async def run_step(
        self,
        weaver_id: str,
        capability_id: str,
        backend: str,
        strand_sets: list[StrandSet],
        requested_outputs: frozenset[str],
    ) -> list[WeaveResult]:
        pool = await self._get_pool()
        payload = [ss.to_json() for ss in strand_sets]
        job = await pool.enqueue_job(
            _FUNCTION_NAME,
            weaver_id,
            capability_id,
            backend,
            payload,
            list(requested_outputs),
            _queue_name=queue_for(weaver_id),
        )
        if job is None:  # pragma: no cover - only on a job-id collision we never set
            raise RuntimeError(f"failed to enqueue weave_step for {weaver_id}")
        results_json = await job.result(timeout=self._result_timeout)
        return [WeaveResult.from_json(r) for r in results_json]
