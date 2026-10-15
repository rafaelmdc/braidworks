"""BackendDispatchWeaver — routes a capability to a named backend strategy.

Holds ``{backend_name: ResolutionBackend}``, dispatches ``execute_batch`` to the
selected backend (raising ``BackendUnavailable`` when absent/unconfigured), then
runs the single shared mapper. Kept in the taxon package for now; promote to a
shared ``weaverkit`` once a second weaver proves the abstraction.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from braidworks.core import (
    BackendUnavailable,
    BaseWeaver,
    UnsupportedCapability,
    WeaveResult,
    map_lookup,
)
from braidworks.core.availability import require_capability
from braidworks.core.http_pacing import validate_request_pacing
from braidworks.core.lifecycle import close_backends

from . import vocab
from .backends.base import ResolutionBackend
from .mapper import map_taxon_match


class BackendDispatchWeaver(BaseWeaver):
    """Routes each capability call to a named backend, then runs the shared mapper."""

    def __init__(self, backends: dict[str, ResolutionBackend]) -> None:
        self._backends = dict(backends)

    async def aclose(self) -> None:
        await close_backends(self._backends.values())

    def _strategy(self, backend: str) -> ResolutionBackend:
        strat = self._backends.get(backend)
        if strat is None or not strat.is_configured():
            raise BackendUnavailable(
                f"backend {backend!r} is not configured for {self.MANIFEST.weaver_id!r}"
            )
        return strat

    def supports_request_pacing(self, backend: str) -> bool:
        return bool(getattr(self._backends.get(backend), "supports_request_pacing", False))

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
            capability_id,
            [strand_set],
            requested_outputs=requested_outputs,
            backend=backend,
            params=params,
        )
        return results[0]

    async def execute_batch(
        self, capability_id, strand_sets, *, requested_outputs, backend, params=None
    ) -> list[WeaveResult]:
        # Today's taxonomy capabilities take no parameters; accepted for the uniform
        # runner contract and ignored. Genome/gene capabilities will thread it to resolve.
        cap = require_capability(self, capability_id, backend)
        validate_request_pacing(self, backend)
        strategy = self._strategy(backend)  # raises BackendUnavailable

        # The list_/describe_ capabilities have a set-of-ids / detail output shape that
        # doesn't fit the TaxonMatch resolver mapper, so they use core's
        # LookupRecord/map_lookup path. Each builds queries, calls a backend method, maps.
        if capability_id in (
            vocab.LIST_CHILDREN,
            vocab.DESCRIBE_TAXON_HISTORY,
            vocab.LIST_GENOMES,
            vocab.DESCRIBE_GENOME,
            vocab.RESOLVE_GENE,
            vocab.DESCRIBE_GENE,
            vocab.LIST_ORTHOLOGS,
        ):
            records = await self._lookup_records(
                capability_id, cap, strand_sets, backend, requested_outputs, params
            )
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

    async def _lookup_records(
        self, capability_id, cap, strand_sets, backend, requested_outputs, params
    ):
        """Run a list_/describe_ capability on the backend, returning LookupRecords."""
        strategy = self._strategy(backend)
        (input_type,) = tuple(cap.consumes)
        queries = [{input_type: self._value(ss, input_type)} for ss in strand_sets]
        effective = cap.resolve_params(params)
        if capability_id == vocab.DESCRIBE_TAXON_HISTORY:
            return await self._operation(strategy, "describe_taxon_history")(queries)
        if capability_id == vocab.LIST_CHILDREN:
            return await self._operation(strategy, "list_children")(
                queries, rank=effective.get("rank")
            )
        if capability_id == vocab.LIST_GENOMES:
            return await self._operation(strategy, "list_genomes")(
                queries,
                reference_only=bool(effective.get("reference_only", False)),
                annotated_only=bool(effective.get("annotated_only", False)),
                assembly_level=effective.get("assembly_level"),
            )
        if capability_id == vocab.RESOLVE_GENE:
            return await self._operation(strategy, "resolve_gene")(
                queries, taxon=effective.get("taxon", "9606")
            )
        if capability_id == vocab.LIST_ORTHOLOGS:
            return await self._operation(strategy, "list_orthologs")(
                queries, taxon_filter=effective.get("taxon_filter")
            )
        # describe_genome / describe_gene: pass the triggered groups so the extra
        # endpoint (sequences / products) is fetched only when its group is requested.
        groups = cap.triggered_groups(requested_outputs)
        if capability_id == vocab.DESCRIBE_GENE:
            return await self._operation(strategy, "describe_gene")(queries, groups=groups)
        return await self._operation(strategy, "describe_genome")(queries, groups=groups)

    @staticmethod
    def _operation(strategy: ResolutionBackend, name: str) -> Callable[..., Any]:
        operation = getattr(strategy, name, None)
        if not callable(operation):
            raise UnsupportedCapability(f"{type(strategy).__name__} does not support {name}")
        return operation

    @staticmethod
    def _value(strand_set, type_id: str):
        strand = strand_set.get(type_id)
        return strand.value if strand is not None else None
