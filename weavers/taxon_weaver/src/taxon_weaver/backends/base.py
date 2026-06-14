"""ResolutionBackend — the taxon-domain backend interface.

Implements core's generic ``BackendStrategy`` (``name`` / ``is_configured`` /
``fingerprint``) and adds the one domain operation: resolve a batch of consumed
values into ``TaxonMatch`` objects, in input order. The dispatch weaver calls
this; core never does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..intermediate import TaxonMatch


class ResolutionBackend(ABC):
    """Taxon-domain backend: a `BackendStrategy` plus a batch `resolve` operation."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this backend is usable in this instance (else BackendUnavailable)."""

    @abstractmethod
    def fingerprint(self) -> str:
        """Per-backend data-state fingerprint for the cache key. Never ``"unknown"``."""

    @abstractmethod
    async def resolve(
        self, capability_id: str, queries: list, *, need_lineage: bool
    ) -> list[TaxonMatch]:
        """Resolve consumed values (names for resolve_name, taxids for describe_taxon).

        Returns exactly one ``TaxonMatch`` per input, in input order.
        """
