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
    # Organism layer (taxon_weaver / gtdb_weaver)
    "ncbi.taxon.id": "NCBI Taxonomy taxid — the primary organism join key.",
    "organism.scientific_name": "Canonical scientific name — clade-keyed joins (e.g. FAPROTAX).",
    "ncbi.taxon.lineage": "Ranked lineage [{taxid,rank,name}] — clade-keyed joins.",
    "ncbi.taxon.rank": "Taxonomic rank (species, genus, …).",
    "gtdb.taxon.id": "GTDB genome-based taxonomy id.",
    # Molecular layer (uniprot_weaver hinge + hubs)
    "protein.query": "Free-text gene symbol / protein name / accession — the molecular entry input.",
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


# Catalog of produced *leaf/payload* outputs that are NOT join keys (nothing
# consumes them) — descriptive fields a weaver emits. Unlike SHARED_KEYS this is a
# naming catalog, not a reachability gate: membership grants no join-eligibility,
# it just keeps output names consistent across weavers (so we don't drift between
# e.g. ``ncbi.taxon.parent_id`` and ``ncbi.parent_taxon_id``). To make a leaf output
# a real join target, *promote* it into SHARED_KEYS (a deliberate edit). See
# weaverkit/docs/decisions.md (Decision F).
OUTPUT_KEYS: dict[str, str] = {
    # taxon_weaver leaf outputs
    "ncbi.taxon.parent_id": "Parent taxid of the resolved node (descriptive).",
    "ncbi.taxon.match_type": "How a name matched (exact/synonym/fuzzy/taxid).",
    "ncbi.taxon.review_required": "Whether the match needs human review (bool).",
    # microbe trait outputs (example_weaver / bacdive_weaver / future trait weavers)
    "microbe.trait.gram_stain": "Gram stain (positive/negative).",
    "microbe.trait.optimum_temp": "Optimum growth temperature.",
    "microbe.trait.metabolism": "Metabolic strategy (aerobe/anaerobe/…).",
    "microbe.trait.cell_shape": "Cell morphology / shape (rod-shaped, coccus-shaped, …).",
    "microbe.trait.motility": "Whether the organism is motile (yes/no).",
    "microbe.trait.spore_formation": "Whether it forms spores (yes/no).",
    "microbe.trait.oxygen_tolerance": "Oxygen relationship (aerobe/anaerobe/facultative/…).",
    "microbe.trait.optimum_ph": "Optimum growth pH.",
    # microbe–disease association outputs (disbiome_weaver)
    "microbe.disease.names": "Distinct disease names a microbe is associated with.",
    "microbe.disease.count": "Number of disease-association experiment records for a microbe.",
    "microbe.disease.associations": "Compact per-experiment microbe–disease rows "
    "(disease, Elevated/Reduced direction, method, sample, host).",
    "microbe.disease.records": "Complete joined Disbiome records — every experiment / "
    "disease / organism / publication field, incl. study-quality metadata.",
    # uniprot_weaver leaf outputs (descriptive protein-entry fields)
    "protein.name": "Recommended protein name (UniProt).",
    "protein.gene": "Primary gene symbol (UniProt).",
    "protein.organism": "Source organism scientific name (UniProt).",
    "protein.function": "Curated function summary (UniProt FUNCTION comment).",
    "protein.length": "Sequence length in amino acids.",
    "protein.reviewed": "Whether the entry is reviewed (Swiss-Prot) vs unreviewed (TrEMBL).",
}


def is_shared_key(type_id: str) -> bool:
    """Whether ``type_id`` is a registered, connectable shared key."""
    return type_id in SHARED_KEYS


def is_known_output(type_id: str) -> bool:
    """Whether ``type_id`` is a known output — a shared key or a catalogued leaf.

    Used for the (advisory, non-failing) output-name check: a produced type_id that
    is neither a shared key nor catalogued is a naming-drift risk worth flagging.
    """
    return type_id in SHARED_KEYS or type_id in OUTPUT_KEYS
