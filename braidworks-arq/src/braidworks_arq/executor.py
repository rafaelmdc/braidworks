"""build_distributed_executor — a LocalExecutor wired to run steps on arq.

The executor *is* core's ``LocalExecutor`` (same orchestration, caching, fallback,
review queue, branch/wave concurrency), just constructed with an ``ArqStepRunner`` so
every weave-step is dispatched to a worker. The orchestrator still needs a registry
for manifests/capabilities/fingerprints (planning and cache keys are local); only the
*execution* of a step moves off-process.
"""

from __future__ import annotations

from typing import Any

from braidworks.core.cache import StrandCache
from braidworks.core.executor import LocalExecutor
from braidworks.core.registry import BraidRegistry

from braidworks_arq.runner import ArqStepRunner


def build_distributed_executor(
    registry: BraidRegistry,
    *,
    cache: StrandCache | None = None,
    pool: Any | None = None,
    result_timeout: float | None = 300.0,
) -> LocalExecutor:
    """A ``LocalExecutor`` that dispatches each weave-step to an arq worker.

    Cardinality fan-out (``execute(..., expand_policy=, expand_by_type=)``) is honored
    unchanged here: the one→many expansion happens in the executor's orchestration, not
    in the step runner, so it composes with this module's batch-across-workers fan-out.
    """
    return LocalExecutor(
        registry,
        cache=cache,
        runner=ArqStepRunner(pool=pool, result_timeout=result_timeout),
    )
