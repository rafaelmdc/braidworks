"""The Celery app: Redis broker/backend, durability settings, per-weaver routing.

Configuration is environment-driven so the same code runs locally and in a fleet:

- ``BRAIDWORKS_BROKER_URL`` / ``BRAIDWORKS_RESULT_BACKEND`` — default both to
  ``redis://localhost:6379/0``.

Durability defaults matter and are deliberate:

- ``task_acks_late`` + ``task_reject_on_worker_lost`` — a step is only acked after
  it finishes, so a worker crash mid-step re-queues the task instead of losing it.
- ``worker_prefetch_multiplier = 1`` — fair dispatch; a worker takes one heavy step
  at a time rather than hoarding a backlog it can't process.
- JSON serialization end to end — strands/results are already JSON-shaped, and it
  keeps messages language- and version-tolerant (no pickle).

Per-weaver queues (``queue_for``) are how data locality and global rate-limiting are
expressed: a worker that has the NCBI database subscribes to the ``ncbi`` queue, and
an upstream-throttled weaver gets its own queue with a sized worker pool.
"""

from __future__ import annotations

import os

from celery import Celery

_DEFAULT_REDIS = "redis://localhost:6379/0"

QUEUE_PREFIX = "weaver."


def queue_for(weaver_id: str) -> str:
    """The dedicated queue name a weaver's steps are routed to."""
    return f"{QUEUE_PREFIX}{weaver_id}"


def _make_app() -> Celery:
    broker = os.environ.get("BRAIDWORKS_BROKER_URL", _DEFAULT_REDIS)
    backend = os.environ.get("BRAIDWORKS_RESULT_BACKEND", _DEFAULT_REDIS)
    celery_app = Celery("braidworks", broker=broker, backend=backend)
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        # Results are an orchestration detail; don't keep them forever.
        result_expires=3600,
        # A step that never returns must not wedge the queue indefinitely.
        task_default_queue="weaver.default",
    )
    return celery_app


app = _make_app()
