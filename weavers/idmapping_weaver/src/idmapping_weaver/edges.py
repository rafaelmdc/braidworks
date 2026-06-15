"""The edge table — the single source of truth for every ID-mapping capability.

Each :class:`Edge` is one typed cross-reference the planner can route: a source id
type → a target id type, realised by one UniProt ID-mapping ``from``/``to`` pair. The
manifest (``vocab``) and the backend dispatch (``backends.api``) are both generated
from this table, so adding an edge is a one-line, reviewable act.

UniProt accession is the hub: the ID-mapping API only maps *into* the hub
(``X -> UniProtKB``) or *out of* it (``UniProtKB_AC-ID -> Y``). Into-hub edges
(``into_hub=True``) run two jobs — reviewed Swiss-Prot for the canonical accession and
full UniProtKB for coverage — and order the result reviewed-first. Out-of-hub edges run
a single job. Batch A ships the into-hub spokes; B/C add the out-of-hub spokes.
"""

from __future__ import annotations

from dataclasses import dataclass

# UniProt ID-mapping programmatic db names (GET rest.uniprot.org/configure/idmapping/fields).
FROM_UNIPROT = "UniProtKB_AC-ID"  # the hub as a *source* db (out-of-hub edges)
TO_UNIPROT = "UniProtKB"  # the hub as a *target* db (into-hub edges, full)
TO_UNIPROT_REVIEWED = "UniProtKB-Swiss-Prot"  # reviewed-only — the canonical accession

ACCESSION = "protein.uniprot.accession"
MAPPING_COUNT = "protein.uniprot.mapping.count"
MAPPING_RECORDS = "protein.uniprot.mapping.records"


@dataclass(frozen=True)
class Edge:
    """One typed ID-mapping cross-reference: ``consumes`` → ``produces`` via ``from_db``/``to_db``."""

    capability: str
    from_db: str
    to_db: str
    consumes: str
    produces: str
    into_hub: bool  # True => reviewed-first dual job (target is UniProtKB)


def _into_hub(capability: str, from_db: str, consumes: str) -> Edge:
    """An ``X -> protein.uniprot.accession`` edge (reviewed-first, dual job)."""
    return Edge(
        capability=capability,
        from_db=from_db,
        to_db=TO_UNIPROT,
        consumes=consumes,
        produces=ACCESSION,
        into_hub=True,
    )


def _out_of_hub(capability: str, to_db: str, produces: str) -> Edge:
    """A ``protein.uniprot.accession -> Y`` edge (single job from the hub)."""
    return Edge(
        capability=capability,
        from_db=FROM_UNIPROT,
        to_db=to_db,
        consumes=ACCESSION,
        produces=produces,
        into_hub=False,
    )


# --- Batch A: into the hub (X -> protein.uniprot.accession) -------------------
EDGES: tuple[Edge, ...] = (
    _into_hub("map_geneid", "GeneID", "gene.ncbi.id"),
    _into_hub("map_ensembl", "Ensembl", "gene.ensembl.id"),
    _into_hub("map_ensembl_protein", "Ensembl_Protein", "protein.ensembl.id"),
    _into_hub("map_gene_name", "Gene_Name", "gene.symbol"),
    _into_hub("map_refseq_protein", "RefSeq_Protein", "refseq.protein.id"),
    _into_hub("map_hgnc", "HGNC", "gene.hgnc.id"),
    _into_hub("map_insdc", "EMBL-GenBank-DDBJ", "nucleotide.insdc.accession"),
    _into_hub("map_pdb", "PDB", "pdb.id"),
    # --- Batch B: out of the hub (protein.uniprot.accession -> Y), core targets -----
    _out_of_hub("map_to_geneid", "GeneID", "gene.ncbi.id"),
    _out_of_hub("map_to_ensembl", "Ensembl", "gene.ensembl.id"),
    _out_of_hub("map_to_ensembl_protein", "Ensembl_Protein", "protein.ensembl.id"),
    _out_of_hub("map_to_kegg", "KEGG", "pathway.kegg.id"),
    _out_of_hub("map_to_reactome", "Reactome", "pathway.reactome.id"),
    _out_of_hub("map_to_refseq_protein", "RefSeq_Protein", "refseq.protein.id"),
)

EDGES_BY_CAPABILITY: dict[str, Edge] = {e.capability: e for e in EDGES}
