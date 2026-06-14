"""The ``weave_step`` task — the only thing that runs on a worker.

It is the off-process body of one ``WeaveStepRunner.run_step`` call: rebuild the
weaver from the worker's registry, run a single ``execute_batch``, return serialized
results. Being a native coroutine, it ``await``s the weaver directly — no event-loop
gymnastics. All policy (backend fallback, caching, classification) lives in the
executor that enqueued it, so the task is idempotent and safe to retry.

``ctx`` is arq's job context: ``ctx["redis"]`` is the worker's async Redis connection
(reused for rate limiting) and ``ctx["job_try"]`` is the 1-based attempt number.
"""

from __future__ import annotations

from typing import Any

import random

from arq.worker import Retry

from braidworks.core.exceptions import BackendConfigurationError, BackendUnavailable
from braidworks.core.strand import StrandSet

from braidworks_arq.discovery import get_registry
from braidworks_arq.ratelimit import TokenBucket, load_limits, rate_for

# Control-flow exceptions: how a backend signals "can't run / misconfigured" so the
# *orchestrator* can fall back to another backend. They must propagate untouched —
# retrying them in-task would defeat fallback and waste backoff.
_NO_RETRY = (BackendUnavailable, BackendConfigurationError)

MAX_TRIES = 3


def _retry_defer(job_try: int) -> float:
    """Exponential backoff with full jitter, so fanned-out retries desynchronize.

    Without jitter, a batch of workers that all 429 at once would retry in lockstep
    and re-storm the upstream. Jitter spreads them across the backoff window.
    """
    base = 2 ** (job_try - 1)
    return base * (0.5 + random.random())


async def _throttle(ctx: dict[str, Any], weaver_id: str, backend: str, cost: float) -> None:
    """Await the cluster-wide token bucket if a rule matches this step.

    ``cost`` is the number of tokens this task should consume — one per expected
    external call (≈ the batch size under the non-batchable assumption), so the bucket
    bounds the aggregate *call* rate across the fleet, not just task dispatch.
    """
    rate = rate_for(load_limits(), weaver_id, backend)
    if rate is None:
        return
    bucket = TokenBucket(
        ctx["redis"],
        key=f"braidworks:rl:{weaver_id}:{backend}",
        rate=rate,
        capacity=max(rate, 1.0),
    )
    await bucket.acquire(cost)


async def weave_step(
    ctx: dict[str, Any],
    weaver_id: str,
    capability_id: str,
    backend: str,
    strand_sets_json: list[dict[str, Any]],
    requested_outputs: list[str],
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run one weave-step batch on this worker; return ``[WeaveResult.to_json(), ...]``.

    Retry policy: control-flow exceptions (:data:`_NO_RETRY`) propagate immediately so
    the orchestrator's backend fallback handles them; any other exception is treated
    as transient and retried with backoff (via arq ``Retry``) until ``MAX_TRIES``.
    """
    registry = get_registry()
    weaver = registry.get_weaver(weaver_id)
    strand_sets = [StrandSet.from_json(d) for d in strand_sets_json]
    requested = frozenset(requested_outputs)

    # One token per expected external call ≈ one per entity (non-batchable worst case).
    await _throttle(ctx, weaver_id, backend, cost=max(1, len(strand_sets)))

    try:
        results = await weaver.execute_batch(
            capability_id,
            strand_sets,
            requested_outputs=requested,
            backend=backend,
            params=params or None,
        )
    except _NO_RETRY:
        raise  # orchestrator-level control flow; never retry, never swallow
    except Exception:  # noqa: BLE001 - transient: retry with backoff, then surface
        tries = ctx.get("job_try", 1)
        if tries >= MAX_TRIES:
            raise
        raise Retry(defer=_retry_defer(tries))
    return [r.to_json() for r in results]
