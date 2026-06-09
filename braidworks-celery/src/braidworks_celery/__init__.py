"""Distributed execution for Braidworks: weave-steps on Celery workers over Redis.

This package plugs into braidworks-core's ``WeaveStepRunner`` seam. The executor
and all its orchestration stay in core, in-process; only the per-step batch call is
dispatched to a worker:

- :data:`app` — the Celery app (Redis broker + result backend; durable acks,
  retries with backoff, per-weaver queues).
- :func:`weave_step` — the task a worker runs: rebuild the local registry, run one
  ``execute_batch``, return serialized results.
- :class:`CeleryStepRunner` — a ``WeaveStepRunner`` the executor calls; it submits
  the step to the weaver's queue and awaits the result.
- :func:`build_distributed_executor` — a ``LocalExecutor`` wired with a
  ``CeleryStepRunner``.
- :func:`build_registry_from_entry_points` / :func:`set_registry` — how a worker
  discovers which weavers it serves (``braidworks.weavers`` entry points).
"""

from braidworks_celery.app import app
from braidworks_celery.discovery import (
    build_registry_from_entry_points,
    get_registry,
    iter_weaver_builders,
    set_registry,
)
from braidworks_celery.executor import build_distributed_executor
from braidworks_celery.runner import CeleryStepRunner
from braidworks_celery.tasks import weave_step

__all__ = [
    "app",
    "weave_step",
    "CeleryStepRunner",
    "build_distributed_executor",
    "build_registry_from_entry_points",
    "get_registry",
    "set_registry",
    "iter_weaver_builders",
]
