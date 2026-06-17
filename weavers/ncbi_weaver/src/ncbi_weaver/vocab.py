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
SPECIES_ID = "ncbi.taxon.species_id"  # species-rank ancestor taxid, derived from lineage
CHILDREN_COUNT = "ncbi.taxon.children_count"  # list_children leaf
CHILDREN_RECORDS = "ncbi.taxon.children_records"  # list_children leaf

GENOME_ACCESSION = "genome.accession"  # the genome join key (list_genomes set output)
ASSEMBLY_COUNT = "genome.assembly.count"
ASSEMBLY_RECORDS = "genome.assembly.records"
ASSEMBLY_TITLE = "genome.assembly.title"
ASSEMBLY_LEVEL = "genome.assembly.level"
ASSEMBLY_ORGANISM = "genome.assembly.organism"
ASSEMBLY_DETAIL = "genome.assembly.detail"
SEQUENCE_RECORDS = "genome.sequence.records"

PROTEIN_QUERY = "protein.query"  # gene symbol input to resolve_gene (shared molecular entry)
GENE_ID = "gene.ncbi.id"  # the NCBI gene join key
GENE_SYMBOL = "gene.symbol"
GENE_NAME = "gene.name"
GENE_TYPE = "gene.type"
GENE_ORGANISM = "gene.organism"
GENE_DETAIL = "gene.detail"
GENE_PRODUCTS = "gene.product.records"
ORTHOLOG_COUNT = "gene.ortholog.count"
ORTHOLOG_RECORDS = "gene.ortholog.records"

# --- output groups ----------------------------------------------------------

NAME_CORE_OUTPUTS = frozenset(
    {TAXON_ID, SCIENTIFIC_NAME, TAXON_RANK, PARENT_ID, MATCH_TYPE, REVIEW_REQUIRED}
)
# species_id is derived from the lineage, so it rides in the same group: requesting it
# triggers the lineage fetch. It lets a species-keyed consumer (e.g. disbiome) be fed a
# strain/subspecies taxid — the planner climbs to the species rank automatically.
LINEAGE_OUTPUTS = frozenset({LINEAGE, SPECIES_ID})

# describe_taxon consumes the taxid, so it does not re-produce ncbi.taxon.id.
TAXID_CORE_OUTPUTS = frozenset({SCIENTIFIC_NAME, TAXON_RANK, PARENT_ID})

WEAVER_ID = "ncbi"
WEAVER_VERSION = "0.2.0"
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
LIST_GENOMES = "ncbi.list_genomes"
DESCRIBE_GENOME = "ncbi.describe_genome"
RESOLVE_GENE = "ncbi.resolve_gene"
DESCRIBE_GENE = "ncbi.describe_gene"
LIST_ORTHOLOGS = "ncbi.list_orthologs"

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


LIST_GENOMES_OUTPUTS = frozenset({GENOME_ACCESSION, ASSEMBLY_COUNT, ASSEMBLY_RECORDS})
ASSEMBLY_GROUP = frozenset({ASSEMBLY_TITLE, ASSEMBLY_LEVEL, ASSEMBLY_ORGANISM, ASSEMBLY_DETAIL})
SEQUENCES_GROUP = frozenset({SEQUENCE_RECORDS})


def list_genomes_capability(*, backends: tuple[str, ...]) -> Capability:
    """``ncbi.list_genomes``: a taxid -> its genome assembly accessions.

    Emits ``genome.accession`` as the set output (fan dimension) — "organism -> every
    assembly, each drillable" — plus a count and compact records. Parameters filter the
    live search (reference genomes only, a specific assembly level, annotated only).
    API-only: NCBI Datasets ``genome/taxon/{taxon}/dataset_report``.
    """
    return Capability(
        id=LIST_GENOMES,
        consumes=frozenset({TAXON_ID}),
        produces=LIST_GENOMES_OUTPUTS,
        output_groups=(OutputGroup(id="genomes", outputs=LIST_GENOMES_OUTPUTS),),
        set_outputs=frozenset({GENOME_ACCESSION}),
        parameters=(
            Parameter(name="reference_only", type="bool", default=False,
                      description="Only NCBI reference/representative genomes."),
            Parameter(name="annotated_only", type="bool", default=False,
                      description="Only assemblies that have annotation."),
            Parameter(name="assembly_level", type="string",
                      description="Filter to a level: Complete Genome / Chromosome / Scaffold / Contig."),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )


def describe_genome_capability(*, backends: tuple[str, ...]) -> Capability:
    """``ncbi.describe_genome``: one genome accession -> its assembly detail.

    Two output groups folding two endpoints: ``assembly`` (the dataset_report — level,
    organism, stats, gene counts) and ``sequences`` (the per-sequence reports). API-only.
    """
    return Capability(
        id=DESCRIBE_GENOME,
        consumes=frozenset({GENOME_ACCESSION}),
        produces=ASSEMBLY_GROUP | SEQUENCES_GROUP,
        output_groups=(
            OutputGroup(id="assembly", outputs=ASSEMBLY_GROUP),
            OutputGroup(id="sequences", outputs=SEQUENCES_GROUP),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )


RESOLVE_GENE_OUTPUTS = frozenset({GENE_ID, GENE_SYMBOL, GENE_NAME, GENE_ORGANISM})
GENE_SUMMARY_GROUP = frozenset({GENE_SYMBOL, GENE_NAME, GENE_TYPE, GENE_ORGANISM, GENE_DETAIL})
GENE_PRODUCTS_GROUP = frozenset({GENE_PRODUCTS})
ORTHOLOG_OUTPUTS = frozenset({GENE_ID, ORTHOLOG_COUNT, ORTHOLOG_RECORDS})


def resolve_gene_capability(*, backends: tuple[str, ...]) -> Capability:
    """``ncbi.resolve_gene``: a gene symbol (+ taxon) -> its NCBI gene id.

    Consumes ``protein.query`` (a gene symbol is a valid molecular query), so it shares
    the molecular entry point and gives a second path into the gene layer. The ``taxon``
    parameter disambiguates the species (default human, 9606). API-only:
    ``gene/symbol/{symbol}/taxon/{taxon}/dataset_report``.
    """
    return Capability(
        id=RESOLVE_GENE,
        consumes=frozenset({PROTEIN_QUERY}),
        produces=RESOLVE_GENE_OUTPUTS,
        output_groups=(OutputGroup(id="gene", outputs=RESOLVE_GENE_OUTPUTS),),
        parameters=(
            Parameter(name="taxon", type="string", default="9606",
                      description="Taxid/name to disambiguate the species (default human)."),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )


def describe_gene_capability(*, backends: tuple[str, ...]) -> Capability:
    """``ncbi.describe_gene``: one NCBI gene id -> its detail.

    Two output groups folding two endpoints: ``summary`` (dataset_report — symbol, name,
    type, organism, chromosomes, xrefs) and ``products`` (product_report — transcripts +
    proteins). API-only.
    """
    return Capability(
        id=DESCRIBE_GENE,
        consumes=frozenset({GENE_ID}),
        produces=GENE_SUMMARY_GROUP | GENE_PRODUCTS_GROUP,
        output_groups=(
            OutputGroup(id="summary", outputs=GENE_SUMMARY_GROUP),
            OutputGroup(id="products", outputs=GENE_PRODUCTS_GROUP),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )


def list_orthologs_capability(*, backends: tuple[str, ...]) -> Capability:
    """``ncbi.list_orthologs``: one NCBI gene id -> its ortholog gene ids across taxa.

    Emits ``gene.ncbi.id`` as the set output (the fan dimension) — "this gene -> its
    ortholog in every species, each drillable". The ``taxon_filter`` parameter narrows
    to a clade. API-only: ``gene/id/{id}/orthologs``.
    """
    return Capability(
        id=LIST_ORTHOLOGS,
        consumes=frozenset({GENE_ID}),
        produces=ORTHOLOG_OUTPUTS,
        output_groups=(OutputGroup(id="orthologs", outputs=ORTHOLOG_OUTPUTS),),
        set_outputs=frozenset({GENE_ID}),
        parameters=(
            Parameter(name="taxon_filter", type="string",
                      description="Restrict orthologs to this taxid/clade (e.g. 40674 mammals)."),
        ),
        backends=backends,
        max_batch_size=MAX_BATCH_SIZE,
    )


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """The NCBI weaver manifest, declaring each capability for the wired backends.

    The genome + ``list_children`` capabilities are API-only (they hit the live NCBI
    Datasets service), so they appear only when the ``api`` backend is wired.
    """
    capabilities = [
        resolve_name_capability(backends=backends),
        describe_taxon_capability(backends=backends),
    ]
    if "api" in backends:
        capabilities.append(list_children_capability(backends=("api",)))
        capabilities.append(list_genomes_capability(backends=("api",)))
        capabilities.append(describe_genome_capability(backends=("api",)))
        capabilities.append(resolve_gene_capability(backends=("api",)))
        capabilities.append(describe_gene_capability(backends=("api",)))
        capabilities.append(list_orthologs_capability(backends=("api",)))
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        capabilities=tuple(capabilities),
    )
