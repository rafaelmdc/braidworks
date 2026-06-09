"""The arq worker entry point: ``arq braidworks_arq.WorkerSettings``.

A worker serves one weaver's queue (data locality — it only needs that weaver's
data). Which queue and which weavers are environment-driven so the same image runs as
any weaver's worker:

- ``BRAIDWORKS_QUEUE`` — the queue to consume (default ``weaver.default``); set it to
  ``queue_for(weaver_id)`` (e.g. ``weaver.ncbi``).
- ``BRAIDWORKS_WEAVERS`` — comma list of weaver ids to load into this worker's
  registry (default: all discovered). Pair it with the queue so a worker loads only
  what it serves.

Durability: ``max_tries`` bounds retries; if a worker dies mid-job arq re-queues it
(the in-progress lock expires), so a crash does not lose the step.
"""

from __future__ import annotations

import os
from typing import Any

from braidworks_arq.discovery import build_registry_from_entry_points, set_registry
from braidworks_arq.settings import QUEUE_PREFIX, redis_settings
from braidworks_arq.tasks import MAX_TRIES, weave_step


async def _on_startup(ctx: dict[str, Any]) -> None:
    spec = os.environ.get("BRAIDWORKS_WEAVERS")
    only = frozenset(s.strip() for s in spec.split(",") if s.strip()) if spec else None
    set_registry(build_registry_from_entry_points(only=only))


class WorkerSettings:
    """arq worker configuration. Run with ``arq braidworks_arq.WorkerSettings``."""

    functions = [weave_step]
    redis_settings = redis_settings()
    queue_name = os.environ.get("BRAIDWORKS_QUEUE", f"{QUEUE_PREFIX}default")
    on_startup = _on_startup
    max_tries = MAX_TRIES
    # Keep results long enough for the orchestrator to fetch them.
    keep_result = 3600
