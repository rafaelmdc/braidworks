"""BackendDispatchWeaver — routes a capability to a named backend, then maps.

Generated boilerplate; you should not need to edit this. It pulls each consumed
input off the StrandSet, hands the batch to the selected backend's ``fetch``, and
runs the single shared mapper over the results.
"""

from __future__ import annotations

from typing import Any

from braidworks.core import (
    BackendUnavailable,
    BaseWeaver,
    UnsupportedCapability,
    WeaveResult,
)

from exampleweaver.backends.base import ExampleBackend
from exampleweaver.mapper import map_record


class BackendDispatchWeaver(BaseWeaver):
    """Routes each capability call to a named backend, then runs the shared mapper."""

    def __init__(self, backends: dict[str, ExampleBackend]) -> None:
        self._backends = dict(backends)

    def _strategy(self, backend: str) -> ExampleBackend:
        strat = self._backends.get(backend)
        if strat is None or not strat.is_configured():
            raise BackendUnavailable(
                f"backend {backend!r} is not configured for {self.MANIFEST.weaver_id!r}"
            )
        return strat

    def backend_fingerprint(self, backend: str) -> str:
        strat = self._backends.get(backend)
        return strat.fingerprint() if strat is not None else f"unconfigured:{backend}"

    async def execute(
        self, capability_id, strand_set, *, requested_outputs, backend
    ) -> WeaveResult:
        results = await self.execute_batch(
            capability_id, [strand_set], requested_outputs=requested_outputs, backend=backend
        )
        return results[0]

    async def execute_batch(
        self, capability_id, strand_sets, *, requested_outputs, backend
    ) -> list[WeaveResult]:
        cap = self.MANIFEST.capability(capability_id)
        if cap is None:
            raise UnsupportedCapability(
                f"{self.MANIFEST.weaver_id!r} has no capability {capability_id!r}"
            )
        strategy = self._strategy(backend)  # raises BackendUnavailable
        consumed = tuple(sorted(cap.consumes))
        queries: list[dict[str, Any]] = [
            {t: (ss.get(t).value if ss.get(t) is not None else None) for t in consumed}
            for ss in strand_sets
        ]
        groups_to_compute = cap.triggered_groups(requested_outputs)
        records = await strategy.fetch(
            capability_id,
            queries,
            requested_outputs=requested_outputs,
            groups_to_compute=groups_to_compute,
        )
        return [
            map_record(
                r,
                capability=cap,
                requested_outputs=requested_outputs,
                backend=backend,
                weaver_version=self.MANIFEST.version,
            )
            for r in records
        ]
