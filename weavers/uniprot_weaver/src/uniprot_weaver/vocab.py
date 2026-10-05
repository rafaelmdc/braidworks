"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import (
    Capability,
    OutputGroup,
    Parameter,
    Provenance,
    WeaverManifest,
)

WEAVER_ID = "uniprot"
WEAVER_VERSION = "0.2.3"
WEAVER_TITLE = "UniProt protein identity (gene/protein query -> accession + taxid + annotation)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.uniprot.org",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/nar/gkac1052",
    attribution="UniProt Consortium",
)


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        capabilities=(
            Capability(
                id="resolve_protein",
                consumes=frozenset({"protein.query"}),
                produces=frozenset(
                    {
                        "ncbi.taxon.id",
                        "protein.function",
                        "protein.gene",
                        "protein.length",
                        "protein.name",
                        "protein.organism",
                        "protein.reviewed",
                        "protein.uniprot.accession",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="identity",
                        outputs=frozenset(
                            {
                                "protein.gene",
                                "protein.name",
                                "protein.organism",
                                "protein.reviewed",
                                "protein.uniprot.accession",
                            }
                        ),
                    ),
                    OutputGroup(id="taxonomy", outputs=frozenset({"ncbi.taxon.id"})),
                    OutputGroup(
                        id="function", outputs=frozenset({"protein.function", "protein.length"})
                    ),
                ),
                backends=backends,
                max_batch_size=25,
                always_computed_groups=frozenset({"identity"}),
                parameters=(
                    Parameter(
                        name="organism",
                        type="string",
                        enum=(),
                        default=None,
                        description="NCBI taxid to constrain the species (e.g. 9606 human, 10090 mouse). A bare gene symbol like TP53 otherwise resolves to whichever species ranks first; unset = any.",
                    ),
                ),
            ),
            Capability(
                id="map_to_accession",
                consumes=frozenset(
                    {
                        "gene.ensembl.id",
                        "gene.hgnc.id",
                        "gene.ncbi.id",
                        "gene.symbol",
                        "nucleotide.insdc.accession",
                        "pdb.id",
                        "protein.ensembl.id",
                        "refseq.protein.id",
                    }
                ),
                produces=frozenset(
                    {
                        "protein.uniprot.accession",
                        "protein.uniprot.mapping.count",
                        "protein.uniprot.mapping.records",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="mapping",
                        outputs=frozenset(
                            {
                                "protein.uniprot.accession",
                                "protein.uniprot.mapping.count",
                                "protein.uniprot.mapping.records",
                            }
                        ),
                    ),
                ),
                backends=backends,
                max_batch_size=1000,
                always_computed_groups=frozenset({"mapping"}),
                set_outputs=frozenset({"protein.uniprot.accession"}),
                consumes_any=True,
            ),
            Capability(
                id="map_from_accession",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "chembl.id",
                        "drugbank.id",
                        "eggnog.group",
                        "gene.ensembl.id",
                        "gene.ncbi.id",
                        "orthodb.group",
                        "pathway.kegg.id",
                        "pathway.reactome.id",
                        "pdb.id",
                        "protein.ensembl.id",
                        "protein.uniprot.mapping.count",
                        "protein.uniprot.mapping.records",
                        "refseq.protein.id",
                        "string.id",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="mapping",
                        outputs=frozenset(
                            {
                                "chembl.id",
                                "drugbank.id",
                                "eggnog.group",
                                "gene.ensembl.id",
                                "gene.ncbi.id",
                                "orthodb.group",
                                "pathway.kegg.id",
                                "pathway.reactome.id",
                                "pdb.id",
                                "protein.ensembl.id",
                                "protein.uniprot.mapping.count",
                                "protein.uniprot.mapping.records",
                                "refseq.protein.id",
                                "string.id",
                            }
                        ),
                    ),
                ),
                backends=backends,
                max_batch_size=1000,
                always_computed_groups=frozenset({"mapping"}),
                set_outputs=frozenset(
                    {
                        "chembl.id",
                        "drugbank.id",
                        "eggnog.group",
                        "gene.ensembl.id",
                        "gene.ncbi.id",
                        "orthodb.group",
                        "pathway.kegg.id",
                        "pathway.reactome.id",
                        "pdb.id",
                        "protein.ensembl.id",
                        "refseq.protein.id",
                        "string.id",
                    }
                ),
            ),
        ),
    )
