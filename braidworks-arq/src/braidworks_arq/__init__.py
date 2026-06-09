"""Distributed execution for Braidworks: weave-steps on arq workers over Redis.

arq is async-native, which matches braidworks end to end — the orchestrator and
weavers are already ``async``, so dispatching a step is just ``await`` all the way
down (no thread bridge, no ``asyncio.run`` per task). This package plugs into core's
``WeaveStepRunner`` seam; the executor and all its orchestration stay in core.

- :func:`weave_step` — the coroutine a worker runs: rebuild the local registry, run
  one ``execute_batch``, return serialized results.
- :class:`ArqStepRunner` — a ``WeaveStepRunner`` the executor calls; it enqueues the
  step on the weaver's queue and awaits the job result.
- :func:`build_distributed_executor` — a ``LocalExecutor`` wired with an
  ``ArqStepRunner``.
- :class:`WorkerSettings` — the arq worker entry point (``arq braidworks_arq.WorkerSettings``).
- :func:`build_registry_from_entry_points` / :func:`set_registry` — how a worker
  discovers which weavers it serves (``braidworks.weavers`` entry points).
"""

from braidworks_arq.discovery import (
    build_registry_from_entry_points,
    get_registry,
    iter_weaver_builders,
    set_registry,
)
from braidworks_arq.executor import build_distributed_executor
from braidworks_arq.runner import ArqStepRunner
from braidworks_arq.settings import queue_for, redis_settings
from braidworks_arq.tasks import weave_step
from braidworks_arq.worker import WorkerSettings

__all__ = [
    "weave_step",
    "ArqStepRunner",
    "build_distributed_executor",
    "WorkerSettings",
    "queue_for",
    "redis_settings",
    "build_registry_from_entry_points",
    "get_registry",
    "set_registry",
    "iter_weaver_builders",
]
