"""The ``weave_step`` task — the only thing that runs on a worker.

It is the off-process body of one ``WeaveStepRunner.run_step`` call: rebuild the
weaver from the worker's registry, run a single ``execute_batch``, return serialized
results. It is deliberately tiny and stateless beyond the (cached) registry — all
policy (backend fallback, caching, classification) lives in the executor that
submitted it, so the task is idempotent and safe to retry.

Async bridge: weavers are ``async`` but Celery tasks are synchronous, so the task
runs the batch with ``asyncio.run``. Each task is a self-contained batch, so a fresh
event loop per task is correct and cheap relative to the I/O it wraps.
"""

from __future__ import annotations

import asyncio
from typing import Any

from braidworks.core.exceptions import BackendConfigurationError, BackendUnavailable
from braidworks.core.strand import StrandSet

from braidworks_celery.app import app
from braidworks_celery.discovery import get_registry
from braidworks_celery.ratelimit import load_limits, rate_for

# Braidworks control-flow exceptions: these are how a backend signals "I can't run /
# I'm misconfigured" so the *orchestrator* can fall back to another backend. They must
# propagate untouched — retrying them in-task would defeat fallback and waste backoff.
_NO_RETRY = (BackendUnavailable, BackendConfigurationError)


def _throttle(weaver_id: str, backend: str) -> None:
    """Block on the cluster-wide token bucket if a rule matches this step."""
    limits = load_limits()
    rate = rate_for(limits, weaver_id, backend)
    if rate is None:
        return
    # Imported lazily so the task has no hard redis dependency unless throttling.
    import redis

    from braidworks_celery.app import app as _app
    from braidworks_celery.ratelimit import TokenBucket

    client = redis.Redis.from_url(_app.conf.broker_url)
    bucket = TokenBucket(
        client, key=f"braidworks:rl:{weaver_id}:{backend}", rate=rate, capacity=max(rate, 1.0)
    )
    bucket.acquire()


@app.task(
    bind=True,
    name="braidworks.weave_step",
    acks_late=True,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def weave_step(
    self,  # noqa: ANN001 - Celery bound task
    weaver_id: str,
    capability_id: str,
    backend: str,
    strand_sets_json: list[dict[str, Any]],
    requested_outputs: list[str],
) -> list[dict[str, Any]]:
    """Run one weave-step batch on this worker; return ``[WeaveResult.to_json(), ...]``.

    Retry policy: control-flow exceptions (:data:`_NO_RETRY`) propagate immediately so
    the orchestrator's backend fallback handles them; any other exception is treated
    as transient and retried with backoff before finally surfacing.
    """
    registry = get_registry()
    weaver = registry.get_weaver(weaver_id)
    strand_sets = [StrandSet.from_json(d) for d in strand_sets_json]
    requested = frozenset(requested_outputs)

    _throttle(weaver_id, backend)

    try:
        results = asyncio.run(
            weaver.execute_batch(
                capability_id,
                strand_sets,
                requested_outputs=requested,
                backend=backend,
            )
        )
    except _NO_RETRY:
        raise  # orchestrator-level control flow; never retry, never swallow
    except Exception as exc:  # noqa: BLE001 - transient: retry with backoff, then surface
        raise self.retry(exc=exc)
    return [r.to_json() for r in results]
