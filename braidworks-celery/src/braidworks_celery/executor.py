"""build_distributed_executor — a LocalExecutor wired to run steps on Celery.

This is the whole point made small: the executor *is* core's ``LocalExecutor`` (same
orchestration, caching, fallback, review queue), just constructed with a
``CeleryStepRunner`` so every weave-step is dispatched to a worker instead of run
in-process. The orchestrator still needs a registry for manifests/capabilities/
fingerprints (planning and cache keys are local); the *execution* is what moves.
"""

from __future__ import annotations

from braidworks.core.cache import StrandCache
from braidworks.core.executor import LocalExecutor
from braidworks.core.registry import BraidRegistry

from braidworks_celery.runner import CeleryStepRunner


def build_distributed_executor(
    registry: BraidRegistry,
    *,
    cache: StrandCache | None = None,
    result_timeout: float | None = 300.0,
) -> LocalExecutor:
    """A ``LocalExecutor`` that dispatches each weave-step to a Celery worker."""
    return LocalExecutor(
        registry,
        cache=cache,
        runner=CeleryStepRunner(result_timeout=result_timeout),
    )
