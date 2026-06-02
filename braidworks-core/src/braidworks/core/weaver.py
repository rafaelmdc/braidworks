"""BaseWeaver — the interface every weaver implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, ClassVar, Hashable, TypeVar

from braidworks.core.capability import WeaverManifest
from braidworks.core.result import WeaveResult
from braidworks.core.strand import StrandSet

K = TypeVar("K", bound=Hashable)


class BaseWeaver(ABC):
    """Async boundary around a concrete data source.

    Subclasses declare a class-level ``MANIFEST`` and implement
    ``dataset_version`` and ``execute``. ``execute_batch`` defaults to a serial
    loop; override it for true batch backends. Weaver state (connections) is
    lazily initialized on first ``execute``, never in ``__init__``.
    """

    MANIFEST: ClassVar[WeaverManifest]

    @abstractmethod
    def dataset_version(self) -> str:
        """Dataset/release version backing this instance. Used in the cache key.

        Return a stable, version-specific string for versioned datasets
        (``"ncbi-taxonomy-2024-03-16"``) or an explicit ``"live"`` /
        ``"unversioned"`` for live sources. Never ``"unknown"`` — that silently
        disables cache invalidation.
        """

    @abstractmethod
    async def execute(
        self,
        capability_id: str,
        strand_set: StrandSet,
        *,
        requested_outputs: frozenset[str],
        backend: str,
    ) -> WeaveResult:
        """Run one capability for one StrandSet. ``backend`` is always concrete."""

    async def execute_batch(
        self,
        capability_id: str,
        strand_sets: list[StrandSet],
        *,
        requested_outputs: frozenset[str],
        backend: str,
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
