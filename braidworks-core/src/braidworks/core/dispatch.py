"""BackendDispatchWeaver — the shared weaver runtime: route to a backend, then map.

The generic 80% of a multi-backend weaver. A concrete weaver subclasses it, sets a
``MANIFEST`` (from its generated ``vocab``) and a ``MAPPER`` (``map_lookup`` or
``map_resolver``), and is done — the routing, batching, input extraction, and
mapping all live here, shared across every weaver. Backends supply the novel part
(``fetch``); see :class:`braidworks.core.backend.BackendBase`.

A weaver that needs to diverge can ignore this and implement ``BaseWeaver``
directly (decisions.md "thin contract, free implementation").
"""

from __future__ import annotations

from typing import Callable, ClassVar

from braidworks.core.backend import BackendBase
from braidworks.core.exceptions import BackendUnavailable, UnsupportedCapability
from braidworks.core.result import WeaveResult
from braidworks.core.strand import StrandSet
from braidworks.core.weaver import BaseWeaver


class BackendDispatchWeaver(BaseWeaver):
    """Routes each capability call to a named backend, then runs the shared mapper.

    Subclass contract: set ``MANIFEST`` (in ``__init__``, from ``vocab``) and
    ``MAPPER`` (a class attribute: ``staticmethod(map_lookup)`` or
    ``staticmethod(map_resolver)``).
    """

    MAPPER: ClassVar[Callable[..., WeaveResult]]

    def __init__(self, backends: dict[str, BackendBase]) -> None:
        if not backends:
            raise ValueError(f"{type(self).__name__} requires at least one backend")
        self._backends = dict(backends)

    def _strategy(self, backend: str) -> BackendBase:
        strat = self._backends.get(backend)
        if strat is None or not strat.is_configured():
            raise BackendUnavailable(
                f"backend {backend!r} is not configured for {self.MANIFEST.weaver_id!r}"
            )
        return strat

    def backend_fingerprint(self, backend: str) -> str:
        strat = self._backends.get(backend)
        # Guard on is_configured(): fingerprint() may read the data source, which an
        # unconfigured backend can't. It never produces a cached result anyway
        # (execute_batch raises BackendUnavailable upstream).
        if strat is None or not strat.is_configured():
            return f"unconfigured:{backend}"
        return strat.fingerprint()

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
        queries = [
            {t: (ss.get(t).value if ss.get(t) is not None else None) for t in consumed}
            for ss in strand_sets
        ]
        # Pre-resolve which output groups are triggered, so the backend keys its
        # fulfillment strategy off a declarative set (decisions.md B).
        groups_to_compute = cap.triggered_groups(requested_outputs)
        records = await strategy.fetch(
            capability_id,
            queries,
            requested_outputs=requested_outputs,
            groups_to_compute=groups_to_compute,
        )
        mapper = type(self).MAPPER
        return [
            mapper(
                r,
                capability=cap,
                requested_outputs=requested_outputs,
                backend=backend,
                weaver_version=self.MANIFEST.version,
                weaver_id=self.MANIFEST.weaver_id,
            )
            for r in records
        ]

    @staticmethod
    def _value(strand_set: StrandSet, type_id: str):
        strand = strand_set.get(type_id)
        return strand.value if strand is not None else None
