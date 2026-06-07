"""The shared-key registry — the canonical strand type_ids weavers may consume.

Reachability guardrail: a weaver is only useful if some other weaver produces a
type it consumes. By requiring every ``consumes`` entry to be a registered shared
key, an agent cannot accidentally build an "island" weaver keyed on a private,
unconnectable type. To add a genuinely new bridge key, add it here in the same PR
(a deliberate, reviewable act) — see docs/weaver-roadmap.md §1 for the join model.
"""

from __future__ import annotations

# type_id -> one-line description (what it identifies / who produces it).
SHARED_KEYS: dict[str, str] = {
    # Entry point
    "organism.name": "Free-text organism name — the entry input (user-provided).",
    # Organism layer (taxonweaver / gtdbweaver)
    "ncbi.taxon.id": "NCBI Taxonomy taxid — the primary organism join key.",
    "organism.scientific_name": "Canonical scientific name — clade-keyed joins (e.g. FAPROTAX).",
    "ncbi.taxon.lineage": "Ranked lineage [{taxid,rank,name}] — clade-keyed joins.",
    "ncbi.taxon.rank": "Taxonomic rank (species, genus, …).",
    "gtdb.taxon.id": "GTDB genome-based taxonomy id.",
    # Molecular layer (uniprotweaver hinge + hubs)
    "protein.uniprot.accession": "UniProt accession — the primary protein join key.",
    "gene.ncbi.id": "NCBI Gene id.",
    "gene.ensembl.id": "Ensembl gene id.",
    "go.term": "Gene Ontology term id.",
    "enzyme.ec": "Enzyme Commission (EC) number.",
    "chem.chebi.id": "ChEBI chemical entity id.",
    "reaction.rhea.id": "Rhea reaction id.",
    "pathway.reactome.id": "Reactome pathway id.",
    "pathway.kegg.id": "KEGG pathway id.",
    "protein.interpro.id": "InterPro entry id.",
    "protein.pfam.id": "Pfam family id.",
    "pdb.id": "PDB / PDBe structure id.",
}


def is_shared_key(type_id: str) -> bool:
    """Whether ``type_id`` is a registered, connectable shared key."""
    return type_id in SHARED_KEYS
