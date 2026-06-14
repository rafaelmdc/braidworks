"""BaseWeaver — the interface every weaver implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, Hashable, Protocol, TypeVar, runtime_checkable

from braidworks.core.capability import WeaverManifest
from braidworks.core.result import WeaveResult
from braidworks.core.strand import StrandSet

K = TypeVar("K", bound=Hashable)


@runtime_checkable
class BackendStrategy(Protocol):
    """Generic identity of one backend a weaver can run a capability against.

    Deliberately domain-neutral: it declares only identity and fingerprint, never
    how an operation executes. Core never calls a backend directly (it calls
    ``weaver.execute_batch``), so there is no ``resolve``/``fetch`` here and no
    assumption that the work is a lookup, transform, join, or anything else.
    Per-domain backend interfaces (e.g. a taxon resolver) extend this in their
    own package.
    """

    name: str

    def is_configured(self) -> bool: ...

    def fingerprint(self) -> str: ...


class BaseWeaver(ABC):
    """Async boundary around a concrete data source.

    Subclasses declare a class-level ``MANIFEST`` and implement
    ``backend_fingerprint`` and ``execute``. ``execute_batch`` defaults to a
    serial loop; override it for true batch backends. Weaver state (connections)
    is lazily initialized on first ``execute``, never in ``__init__``.
    """

    MANIFEST: ClassVar[WeaverManifest]

    @abstractmethod
    def backend_fingerprint(self, backend: str) -> str:
        """Fingerprint of the named backend's data state. Used in the cache key.

        Per-backend by design: a multi-backend weaver's ``"local"`` and ``"api"``
        backends have independent versions. Return a stable, version-specific
        string for versioned datasets (``"ncbi-taxonomy-2024-03-16"``) or an
        explicit ``"live"`` / ``"datasets-v2"`` for live sources. Never
        ``"unknown"`` — that silently disables cache invalidation.
        """

    @abstractmethod
    async def execute(
        self,
        capability_id: str,
        strand_set: StrandSet,
        *,
        requested_outputs: frozenset[str],
        backend: str,
        params: dict[str, Any] | None = None,
    ) -> WeaveResult:
        """Run one capability for one StrandSet. ``backend`` is always concrete.

        ``params`` is the effective per-query parameter map (already validated and
        defaulted by the executor against the capability's declared ``parameters``);
        ``None``/empty means the historical no-options behaviour.
        """

    async def execute_batch(
        self,
        capability_id: str,
        strand_sets: list[StrandSet],
        *,
        requested_outputs: frozenset[str],
        backend: str,
        params: dict[str, Any] | None = None,
    ) -> list[WeaveResult]:
        """Run a capability over many StrandSets.

        Hard contract: returns exactly one result per input, in input order.
        Default implementation is a serial loop; override for real batch.
        """
        results: list[WeaveResult] = []
        for strand_set in strand_sets:
            results.append(
                await self.execute(
                    capability_id,
                    strand_set,
                    requested_outputs=requested_outputs,
                    backend=backend,
                    params=params,
                )
            )
        return results

    @staticmethod
    def _reorder_by_key(
        results_map: dict[K, WeaveResult],
        original_keys: list[K],
        missing_factory: Callable[[K], WeaveResult],
    ) -> list[WeaveResult]:
        """Realign keyed API results to input order, filling gaps with NO_MATCH.

        For weavers whose backend returns results keyed by some identifier rather
        than in input order. Missing keys get ``missing_factory(key)`` at the
        correct position. Does not handle duplicate keys — de-duplicate first.
        """
        return [
            results_map[key] if key in results_map else missing_factory(key)
            for key in original_keys
        ]
