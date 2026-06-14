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
    map_lookup,
)

from . import vocab
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
        # raises BackendUnavailable and the executor falls back). Guard on
        # is_configured() before calling fingerprint(), which may read the data
        # source (e.g. the local backend queries the DB for its build version).
        if strat is None or not strat.is_configured():
            return f"unconfigured:{backend}"
        return strat.fingerprint()

    async def execute(
        self, capability_id, strand_set, *, requested_outputs, backend, params=None
    ) -> WeaveResult:
        results = await self.execute_batch(
            capability_id, [strand_set], requested_outputs=requested_outputs,
            backend=backend, params=params,
        )
        return results[0]

    async def execute_batch(
        self, capability_id, strand_sets, *, requested_outputs, backend, params=None
    ) -> list[WeaveResult]:
        # Today's taxonomy capabilities take no parameters; accepted for the uniform
        # runner contract and ignored. Genome/gene capabilities will thread it to resolve.
        cap = self.MANIFEST.capability(capability_id)
        if cap is None:
            raise UnsupportedCapability(
                f"{self.MANIFEST.weaver_id!r} has no capability {capability_id!r}"
            )
        strategy = self._strategy(backend)  # raises BackendUnavailable

        # list_children has a different output shape (a set of child taxids), so it
        # uses core's LookupRecord/map_lookup path rather than the TaxonMatch mapper.
        if capability_id == vocab.LIST_CHILDREN:
            effective = cap.resolve_params(params)
            queries = [
                {vocab.TAXON_ID: self._value(ss, vocab.TAXON_ID)} for ss in strand_sets
            ]
            records = await strategy.list_children(queries, rank=effective.get("rank"))
            return [
                map_lookup(
                    r,
                    capability=cap,
                    requested_outputs=requested_outputs,
                    backend=backend,
                    weaver_version=self.MANIFEST.version,
                    weaver_id=self.MANIFEST.weaver_id,
                )
                for r in records
            ]

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
