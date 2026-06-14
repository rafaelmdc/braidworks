"""Strand type IDs and the capability/manifest shape for NCBITaxonWeaver.

Shared by the mapper (which produces these strands) and the weaver (which
declares them in its manifest), so the vocabulary lives in exactly one place.
"""

from __future__ import annotations

from braidworks.core import (
    Capability,
    OutputGroup,
    Parameter,
    Provenance,
    WeaverManifest,
)

# --- type IDs ---------------------------------------------------------------

ORGANISM_NAME = "organism.name"  # input to ncbi.resolve_name

TAXON_ID = "ncbi.taxon.id"
SCIENTIFIC_NAME = "organism.scientific_name"
TAXON_RANK = "ncbi.taxon.rank"
PARENT_ID = "ncbi.taxon.parent_id"
MATCH_TYPE = "ncbi.taxon.match_type"
REVIEW_REQUIRED = "ncbi.taxon.review_required"
LINEAGE = "ncbi.taxon.lineage"
CHILDREN_COUNT = "ncbi.taxon.children_count"  # list_children leaf
CHILDREN_RECORDS = "ncbi.taxon.children_records"  # list_children leaf

# --- output groups ----------------------------------------------------------

NAME_CORE_OUTPUTS = frozenset(
    {TAXON_ID, SCIENTIFIC_NAME, TAXON_RANK, PARENT_ID, MATCH_TYPE, REVIEW_REQUIRED}
)
LINEAGE_OUTPUTS = frozenset({LINEAGE})

# describe_taxon consumes the taxid, so it does not re-produce ncbi.taxon.id.
TAXID_CORE_OUTPUTS = frozenset({SCIENTIFIC_NAME, TAXON_RANK, PARENT_ID})

WEAVER_ID = "ncbi"
WEAVER_VERSION = "0.1.6"
WEAVER_TITLE = "NCBI Taxonomy resolver (name/taxid -> taxonomy + lineage)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.ncbi.nlm.nih.gov/taxonomy",
    license="Public Domain",
    citation="",
    attribution="NCBI Taxonomy",
)

RESOLVE_NAME = "ncbi.resolve_name"
DESCRIBE_TAXON = "ncbi.describe_taxon"
LIST_CHILDREN = "ncbi.list_children"

# NCBI Datasets v2 caps batch requests at 1000 taxons; the local backend handles
# any size, so the stricter API limit governs the shared capability.
MAX_BATCH_SIZE = 1000


def resolve_name_capability(*, backends: tuple[str, ...]) -> Capability:
    """The ``ncbi.resolve_name`` capability (organism name -> core + lineage)."""
    return Capability(
        id=RESOLVE_NAME,
        consumes=frozenset({ORGANISM_NAME}),
        produces=NAME_CORE_OUTPUTS | LINEAGE_OUTPUTS,
        output_groups=(
            OutputGroup(id="core", outputs=NAME_CORE_OUTPUTS),
            OutputGroup(id="lineage", outputs=LINEAGE_OUTPUTS),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )


def describe_taxon_capability(*, backends: tuple[str, ...]) -> Capability:
    """The ``ncbi.describe_taxon`` capability (tax id -> core + lineage)."""
    return Capability(
        id=DESCRIBE_TAXON,
        consumes=frozenset({TAXON_ID}),
        produces=TAXID_CORE_OUTPUTS | LINEAGE_OUTPUTS,
        output_groups=(
            OutputGroup(id="core", outputs=TAXID_CORE_OUTPUTS),
            OutputGroup(id="lineage", outputs=LINEAGE_OUTPUTS),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )


CHILDREN_OUTPUTS = frozenset({TAXON_ID, CHILDREN_COUNT, CHILDREN_RECORDS})


def list_children_capability(*, backends: tuple[str, ...]) -> Capability:
    """``ncbi.list_children``: a taxid -> its descendant taxids of a given rank.

    Emits ``ncbi.taxon.id`` as a **set output** (the fan dimension), so a caller can
    fan out one child per descendant — "genus -> all species, each drillable". The
    ``rank`` parameter (default ``species``) selects which descendant rank to return.
    API-only: NCBI Datasets ``dataset_report?children=true`` walks the subtree.
    """
    return Capability(
        id=LIST_CHILDREN,
        consumes=frozenset({TAXON_ID}),
        produces=CHILDREN_OUTPUTS,
        output_groups=(OutputGroup(id="children", outputs=CHILDREN_OUTPUTS),),
        set_outputs=frozenset({TAXON_ID}),
        parameters=(
            Parameter(
                name="rank",
                type="string",
                default="species",
                description="Descendant rank to return (e.g. species, genus, strain).",
            ),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """The NCBI weaver manifest, declaring each capability for the wired backends.

    ``list_children`` is API-only (it walks the live taxonomy subtree), so it appears
    only when the ``api`` backend is wired.
    """
    capabilities = [
        resolve_name_capability(backends=backends),
        describe_taxon_capability(backends=backends),
    ]
    if "api" in backends:
        capabilities.append(list_children_capability(backends=("api",)))
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        capabilities=tuple(capabilities),
    )
