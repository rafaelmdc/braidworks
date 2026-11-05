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
WEAVER_VERSION = "0.2.12"
WEAVER_TITLE = "UniProt protein identity, exact sequence/annotation description and ID mapping"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://www.uniprot.org",
    license="CC-BY-4.0",
    citation="https://doi.org/10.1093/nar/gkac1052",
    attribution="UniProt Consortium",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "chembl.id": "This protein's ChEMBL target id.",
    "drugbank.id": "This protein's DrugBank id.",
    "eggnog.group": "This protein's eggNOG orthologous-group id.",
    "gene.ensembl.id": "Ensembl gene id for one gene.",
    "gene.hgnc.id": "HGNC id for one human gene.",
    "gene.ncbi.id": "NCBI Gene id for one gene.",
    "gene.symbol": "A gene's official symbol, e.g. TP53 — joins gene databases.",
    "ncbi.taxon.id": "NCBI Taxonomy id for one organism — the main organism join key.",
    "nucleotide.insdc.accession": "INSDC nucleotide accession (GenBank/EMBL/DDBJ).",
    "orthodb.group": "This protein's OrthoDB orthologous-group id.",
    "pathway.kegg.id": "A KEGG pathway id.",
    "pathway.reactome.id": "A Reactome pathway id.",
    "pdb.id": "A PDB / PDBe structure id.",
    "protein.annotation.records": "Structured UniProtKB comments/features/references and observed evidence/release metadata.",
    "protein.ensembl.id": "Ensembl protein id for one protein.",
    "protein.function": "What this protein does — UniProt's curated summary.",
    "protein.gene": "The gene that codes for this protein.",
    "protein.length": "This protein's length in amino acids.",
    "protein.name": "This protein's recommended name.",
    "protein.organism": "The organism this protein comes from.",
    "protein.query": "The text you start from — a gene symbol, protein name, or accession.",
    "protein.reviewed": "Whether this entry is reviewed (Swiss-Prot) or not (TrEMBL).",
    "protein.sequence": "Canonical UniProtKB entry amino-acid sequence; produced by describe_protein.",
    "protein.uniprot.accession": "UniProt accession for one protein — the main protein join key.",
    "protein.uniprot.mapping.count": "How many ids this protein mapped to.",
    "protein.uniprot.mapping.records": "The ids this protein mapped to — id plus reviewed/db.",
    "refseq.protein.id": "NCBI RefSeq protein accession (NP_/XP_) for one protein.",
    "string.id": "Taxon-scoped STRING protein ID; produced by STRING interactions and UniProt mapping.",
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
                id="describe_protein",
                consumes=frozenset({"protein.uniprot.accession"}),
                produces=frozenset(
                    {
                        "ncbi.taxon.id",
                        "protein.annotation.records",
                        "protein.function",
                        "protein.gene",
                        "protein.length",
                        "protein.name",
                        "protein.organism",
                        "protein.reviewed",
                        "protein.sequence",
                        "protein.uniprot.accession",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="identity",
                        outputs=frozenset(
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
                    ),
                    OutputGroup(id="sequence", outputs=frozenset({"protein.sequence"})),
                    OutputGroup(
                        id="annotations", outputs=frozenset({"protein.annotation.records"})
                    ),
                ),
                backends=backends,
                max_batch_size=25,
                always_computed_groups=frozenset({"identity"}),
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
                        "string.id",
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
                totals={"protein.uniprot.mapping.records": "protein.uniprot.mapping.count"},
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
                    OutputGroup(id="gene_ncbi_id", outputs=frozenset({"gene.ncbi.id"})),
                    OutputGroup(id="gene_ensembl_id", outputs=frozenset({"gene.ensembl.id"})),
                    OutputGroup(id="protein_ensembl_id", outputs=frozenset({"protein.ensembl.id"})),
                    OutputGroup(id="pathway_kegg_id", outputs=frozenset({"pathway.kegg.id"})),
                    OutputGroup(
                        id="pathway_reactome_id", outputs=frozenset({"pathway.reactome.id"})
                    ),
                    OutputGroup(id="refseq_protein_id", outputs=frozenset({"refseq.protein.id"})),
                    OutputGroup(id="orthodb_group", outputs=frozenset({"orthodb.group"})),
                    OutputGroup(id="eggnog_group", outputs=frozenset({"eggnog.group"})),
                    OutputGroup(id="chembl_id", outputs=frozenset({"chembl.id"})),
                    OutputGroup(id="drugbank_id", outputs=frozenset({"drugbank.id"})),
                    OutputGroup(id="pdb_id", outputs=frozenset({"pdb.id"})),
                    OutputGroup(id="string_id", outputs=frozenset({"string.id"})),
                    OutputGroup(
                        id="summary",
                        outputs=frozenset(
                            {"protein.uniprot.mapping.count", "protein.uniprot.mapping.records"}
                        ),
                    ),
                ),
                backends=backends,
                max_batch_size=1000,
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
                totals={"protein.uniprot.mapping.records": "protein.uniprot.mapping.count"},
            ),
        ),
    )
