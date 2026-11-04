"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import (
    Capability,
    OutputGroup,
    Provenance,
    WeaverManifest,
)

WEAVER_ID = "gtdb"
WEAVER_VERSION = "0.2.12"
WEAVER_TITLE = "GTDB genome-based taxonomy (NCBI taxid / name -> GTDB species + lineage)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://gtdb.ecogenomic.org",
    license="CC-BY-SA-4.0",
    citation="https://doi.org/10.1093/nar/gkab776",
    attribution="GTDB (Genome Taxonomy Database), Parks et al.",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "genome.accession": "NCBI genome assembly accession (GCF_/GCA_) — the genome join key.",
    "gtdb.genome.history": "Observed GTDB genome-specific history, distinct from species/tree assertions.",
    "gtdb.genome.identity": "Observed GTDB genome-specific identity, distinct from species/tree assertions.",
    "gtdb.genome.quality": "Observed GTDB genome-specific quality, distinct from species/tree assertions.",
    "gtdb.genome.representative": "Selected species representative accession with source/release provenance; not necessarily the input strain.",
    "gtdb.genome.synonyms": "Observed GTDB genome-specific synonyms, distinct from species/tree assertions.",
    "gtdb.lineage": "This organism's GTDB genome-based, rank-normalized lineage — an ordered list of {rank, name} from domain to species.",
    "gtdb.taxon.id": "GTDB genome-based taxonomy id for one organism.",
    "gtdb.tree.rootpath": "This organism's path from the root of the GTDB reference tree to its species-representative leaf — an ordered list of [node_id, cumulative_depth]. Two paths give a patristic distance via their deepest shared node (gtdb_weaver.cophenetic).",
    "ncbi.taxon.id": "NCBI Taxonomy id for one organism — the main organism join key.",
    "organism.scientific_name": "An organism's canonical scientific name — joins clade-keyed datasets.",
}


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        type_descriptions=dict(TYPE_DESCRIPTIONS),
        capabilities=(
            Capability(
                id="describe_gtdb_taxonomy",
                consumes=frozenset({"ncbi.taxon.id", "organism.scientific_name"}),
                produces=frozenset({"gtdb.genome.representative", "gtdb.lineage", "gtdb.taxon.id"}),
                output_groups=(
                    OutputGroup(id="core", outputs=frozenset({"gtdb.taxon.id"})),
                    OutputGroup(id="lineage", outputs=frozenset({"gtdb.lineage"})),
                    OutputGroup(
                        id="representative", outputs=frozenset({"gtdb.genome.representative"})
                    ),
                ),
                backends=backends,
                max_batch_size=50,
                consumes_any=True,
            ),
            Capability(
                id="describe_gtdb_tree_placement",
                consumes=frozenset({"ncbi.taxon.id", "organism.scientific_name"}),
                produces=frozenset({"gtdb.tree.rootpath"}),
                output_groups=(OutputGroup(id="core", outputs=frozenset({"gtdb.tree.rootpath"})),),
                backends=tuple(b for b in ("local",) if b in backends),
                max_batch_size=50,
                consumes_any=True,
            ),
            Capability(
                id="describe_genome",
                consumes=frozenset({"genome.accession"}),
                produces=frozenset(
                    {
                        "gtdb.genome.history",
                        "gtdb.genome.identity",
                        "gtdb.genome.quality",
                        "gtdb.genome.synonyms",
                    }
                ),
                output_groups=(
                    OutputGroup(id="identity", outputs=frozenset({"gtdb.genome.identity"})),
                    OutputGroup(id="quality", outputs=frozenset({"gtdb.genome.quality"})),
                    OutputGroup(id="synonyms", outputs=frozenset({"gtdb.genome.synonyms"})),
                    OutputGroup(id="history", outputs=frozenset({"gtdb.genome.history"})),
                ),
                backends=tuple(b for b in ("api",) if b in backends),
                max_batch_size=50,
                always_computed_groups=frozenset({"identity"}),
            ),
        ),
    )
