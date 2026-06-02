"""Shared test fixtures/builders mirroring the TaxonWeaver capability shape."""

from __future__ import annotations

from braidworks.core.capability import Capability, OutputGroup, WeaverManifest

CORE_OUTPUTS = frozenset(
    {
        "ncbi.taxon.id",
        "organism.scientific_name",
        "ncbi.taxon.rank",
        "ncbi.taxon.parent_id",
        "ncbi.taxon.match_type",
        "ncbi.taxon.review_required",
    }
)
LINEAGE_OUTPUTS = frozenset({"ncbi.taxon.lineage"})


def resolve_name_capability(
    *, backends: tuple[str, ...] = ("local",), max_batch_size: int | None = None
) -> Capability:
    """The ``ncbi.resolve_name`` capability: one input, core + lineage groups."""
    return Capability(
        id="ncbi.resolve_name",
        consumes=frozenset({"organism.name"}),
        produces=CORE_OUTPUTS | LINEAGE_OUTPUTS,
        output_groups=(
            OutputGroup(id="core", outputs=CORE_OUTPUTS),
            OutputGroup(id="lineage", outputs=LINEAGE_OUTPUTS),
        ),
        backends=backends,
        max_batch_size=max_batch_size,
    )


def manifest(*capabilities: Capability, weaver_id: str = "ncbi", version: str = "1.0.0") -> WeaverManifest:
    return WeaverManifest(weaver_id=weaver_id, version=version, capabilities=tuple(capabilities))
