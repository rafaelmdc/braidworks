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
    # protein-protein interaction outputs (string_weaver)
    "protein.interaction.partners": "Names of a protein's interaction partners (STRING).",
    "protein.interaction.count": "Number of interaction partners returned (STRING).",
    "protein.interaction.records": "Full STRING interaction edges - partner, combined "
    "score, and per-evidence-channel subscores.",
    # Gene Ontology annotation outputs (quickgo_weaver), grouped by GO aspect
    "go.molecular_function": "GO molecular-function term names annotated to a protein.",
    "go.biological_process": "GO biological-process term names annotated to a protein.",
    "go.cellular_component": "GO cellular-component term names annotated to a protein.",
    "go.count": "Number of distinct GO terms annotated to a protein.",
    "go.records": "Full distinct GO annotations - GO id, name, and aspect.",
    # one GO term's detail (quickgo_weaver describe_go_term — consumes go.term)
    "go.term.name": "Name/label of a single GO term.",
    "go.term.aspect": "GO aspect of a term (molecular_function/biological_process/cellular_component).",
    "go.term.definition": "Textual definition of a single GO term.",
    "go.term.detail": "Full GO term object — name, aspect, definition, synonyms.",
    # experimental-structure outputs (pdbe_weaver)
    "structure.pdb.ids": "PDB ids of experimental structures covering a protein (best first).",
    "structure.pdb.count": "Number of distinct PDB structures covering a protein.",
    "structure.pdb.records": "Distinct PDB structures - id, method, resolution, coverage.",
    # one PDB structure's detail (pdbe_weaver describe_structure — consumes pdb.id)
    "structure.pdb.title": "Title of a single PDB structure.",
    "structure.pdb.method": "Primary experimental method of a single PDB structure.",
    "structure.pdb.release_date": "Release date of a single PDB structure.",
    "structure.pdb.detail": "Full PDB entry detail — title, method, release/deposition date, authors.",
    # predicted-structure outputs (alphafold_weaver)
    "structure.alphafold.entry_id": "AlphaFold DB entry id for a protein's predicted model.",
    "structure.alphafold.mean_plddt": "Mean pLDDT confidence (0-100) of the AlphaFold model.",
    "structure.alphafold.model_url": "URL of the AlphaFold predicted model file (PDB).",
    "structure.alphafold.pae_image_url": "URL of the AlphaFold predicted-aligned-error plot.",
    "structure.alphafold.version": "AlphaFold DB model version.",
    "structure.alphafold.records": "Full AlphaFold model metadata - id, confidence breakdown, URLs.",
    # biological-pathway outputs (reactome_weaver)
    "pathway.reactome.names": "Names of Reactome pathways a protein participates in.",
    "pathway.reactome.count": "Number of distinct Reactome pathways for a protein.",
    "pathway.reactome.records": "Distinct Reactome pathways - stable id, name, in-disease flag.",
    # one Reactome pathway's detail (reactome_weaver describe_pathway — consumes pathway.reactome.id)
    "pathway.reactome.display_name": "Display name of a single Reactome pathway.",
    "pathway.reactome.species": "Species a single Reactome pathway belongs to.",
    "pathway.reactome.in_disease": "Whether a single Reactome pathway is disease-associated (bool).",
    "pathway.reactome.detail": "Full Reactome pathway object — name, species, disease flag, type.",
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
