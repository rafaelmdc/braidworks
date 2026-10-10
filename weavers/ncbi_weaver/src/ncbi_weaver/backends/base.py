"""ResolutionBackend — the taxon-domain backend interface.

Implements core's generic ``BackendStrategy`` (``name`` / ``is_configured`` /
``fingerprint``) and describes structural source-local responsibilities: resolve a batch of consumed
values into ``TaxonMatch`` objects, in input order. The dispatch weaver calls
this; core never does.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from braidworks.core import LookupRecord

from ..intermediate import TaxonMatch


@runtime_checkable
class ResolutionBackend(Protocol):
    """Taxon-domain backend: a `BackendStrategy` plus a batch `resolve` operation."""

    name: str

    def is_configured(self) -> bool:
        """Whether this backend is usable in this instance (else BackendUnavailable)."""

    def fingerprint(self) -> str:
        """Per-backend data-state fingerprint for the cache key. Never ``"unknown"``."""

    async def resolve(
        self, capability_id: str, queries: list, *, need_lineage: bool
    ) -> list[TaxonMatch]:
        """Resolve consumed values (names for resolve_name, taxids for describe_taxon).

        Returns exactly one ``TaxonMatch`` per input, in input order.
        """


@runtime_checkable
class TaxonomyHistoryBackend(Protocol):
    """Optional local dump history, independent of current taxonomy resolution."""

    async def describe_taxon_history(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        """Describe requested/current IDs, merge chains, deletion and source availability."""
        ...


@runtime_checkable
class TaxonomyChildrenBackend(Protocol):
    """Optional descendant listing, separate from taxonomy resolution."""

    async def list_children(
        self, queries: list[dict[str, Any]], *, rank: str
    ) -> list[LookupRecord]:
        """List each input taxid's descendant taxids of ``rank`` (one record per input).

        Only the API backend implements this (it walks the live taxonomy subtree); the
        capability is declared API-only, so a non-API backend is never asked.
        """
        ...


@runtime_checkable
class GenomeBackend(Protocol):
    """Genome listing/detail operations supplied by Datasets."""

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
        ...

    async def describe_genome(
        self, queries: list[dict[str, Any]], *, groups: frozenset[str]
    ) -> list[LookupRecord]:
        """Describe each input genome accession (assembly detail; sequences if asked).

        API-only; a non-API backend is never asked.
        """
        ...


@runtime_checkable
class GeneBackend(Protocol):
    """Gene resolution/detail/ortholog operations supplied by Datasets."""

    async def resolve_gene(
        self, queries: list[dict[str, Any]], *, taxon: str
    ) -> list[LookupRecord]:
        """Resolve each input gene symbol (in ``taxon``) to its NCBI gene id. API-only."""
        ...

    async def describe_gene(
        self, queries: list[dict[str, Any]], *, groups: frozenset[str]
    ) -> list[LookupRecord]:
        """Describe each input gene id (summary; products if that group is asked). API-only."""
        ...

    async def list_orthologs(
        self, queries: list[dict[str, Any]], *, taxon_filter: str | None = None
    ) -> list[LookupRecord]:
        """List each input gene id's ortholog gene ids across taxa. API-only."""
        ...
