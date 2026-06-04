"""BackendDispatchWeaver — routes a capability to a named backend strategy.

Holds ``{backend_name: ResolutionBackend}``, dispatches ``execute_batch`` to the
selected backend (raising ``BackendUnavailable`` when absent/unconfigured), then
runs the single shared mapper. Kept in the taxon package for now; promote to a
shared ``weaverkit`` once a second weaver proves the abstraction.
"""

from __future__ import annotations

from braidworks.core import (
    BaseWeaver,
    BackendUnavailable,
    UnsupportedCapability,
    WeaveResult,
)

from .backends.base import ResolutionBackend
from .mapper import map_taxon_match


class BackendDispatchWeaver(BaseWeaver):
    """Routes each capability call to a named backend, then runs the shared mapper."""

    def __init__(self, backends: dict[str, ResolutionBackend]) -> None:
        self._backends = dict(backends)

    def _strategy(self, backend: str) -> ResolutionBackend:
        strat = self._backends.get(backend)
        if strat is None or not strat.is_configured():
            raise BackendUnavailable(
                f"backend {backend!r} is not configured for {self.MANIFEST.weaver_id!r}"
            )
        return strat

    def backend_fingerprint(self, backend: str) -> str:
        strat = self._backends.get(backend)
        # A declared-but-unconfigured backend still needs a stable, non-"unknown"
        # key value; it will never actually produce a cached result (execute_batch
        # raises BackendUnavailable and the executor falls back).
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
        need_lineage = "lineage" in cap.triggered_groups(requested_outputs)
        (input_type,) = tuple(cap.consumes)  # MVP: single-input capabilities only
        queries = [self._value(ss, input_type) for ss in strand_sets]
        matches = await strategy.resolve(capability_id, queries, need_lineage=need_lineage)
        return [
            map_taxon_match(
                m,
                capability=cap,
                requested_outputs=requested_outputs,
                backend=backend,
                weaver_version=self.MANIFEST.version,
            )
            for m in matches
        ]

    @staticmethod
    def _value(strand_set, type_id: str):
        strand = strand_set.get(type_id)
        return strand.value if strand is not None else None
