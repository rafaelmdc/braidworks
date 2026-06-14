"""ResolutionBackend — the taxon-domain backend interface.

Implements core's generic ``BackendStrategy`` (``name`` / ``is_configured`` /
``fingerprint``) and adds the one domain operation: resolve a batch of consumed
values into ``TaxonMatch`` objects, in input order. The dispatch weaver calls
this; core never does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from braidworks.core import LookupRecord, UnsupportedCapability

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

    async def list_children(
        self, queries: list[dict[str, Any]], *, rank: str
    ) -> list[LookupRecord]:
        """List each input taxid's descendant taxids of ``rank`` (one record per input).

        Only the API backend implements this (it walks the live taxonomy subtree); the
        capability is declared API-only, so a non-API backend is never asked.
        """
        raise UnsupportedCapability(
            f"{type(self).__name__} does not support list_children"
        )

    async def list_genomes(
        self,
        queries: list[dict[str, Any]],
        *,
        reference_only: bool = False,
        annotated_only: bool = False,
        assembly_level: str | None = None,
    ) -> list[LookupRecord]:
        """List each input taxid's genome assembly accessions (one record per input).

        API-only (live NCBI Datasets search); a non-API backend is never asked.
        """
        raise UnsupportedCapability(
            f"{type(self).__name__} does not support list_genomes"
        )

    async def describe_genome(
        self, queries: list[dict[str, Any]], *, groups: frozenset[str]
    ) -> list[LookupRecord]:
        """Describe each input genome accession (assembly detail; sequences if asked).

        API-only; a non-API backend is never asked.
        """
        raise UnsupportedCapability(
            f"{type(self).__name__} does not support describe_genome"
        )

    async def resolve_gene(
        self, queries: list[dict[str, Any]], *, taxon: str
    ) -> list[LookupRecord]:
        """Resolve each input gene symbol (in ``taxon``) to its NCBI gene id. API-only."""
        raise UnsupportedCapability(
            f"{type(self).__name__} does not support resolve_gene"
        )

    async def describe_gene(
        self, queries: list[dict[str, Any]], *, groups: frozenset[str]
    ) -> list[LookupRecord]:
        """Describe each input gene id (summary; products if that group is asked). API-only."""
        raise UnsupportedCapability(
            f"{type(self).__name__} does not support describe_gene"
        )

    async def list_orthologs(
        self, queries: list[dict[str, Any]], *, taxon_filter: str | None = None
    ) -> list[LookupRecord]:
        """List each input gene id's ortholog gene ids across taxa. API-only."""
        raise UnsupportedCapability(
            f"{type(self).__name__} does not support list_orthologs"
        )
