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
    "organism.name": "The text you start from — an organism name.",
    # Organism layer (ncbi_weaver / gtdb_weaver)
    "ncbi.taxon.id": "NCBI Taxonomy id for one organism — the main organism join key.",
    "ncbi.taxon.species_id": "The species-rank taxid for an organism (a strain/subspecies climbs to its species) — the join key for species-level datasets.",
    "organism.scientific_name": "An organism's canonical scientific name — joins clade-keyed datasets.",
    "ncbi.taxon.lineage": "An organism's ranked lineage, from species up to root.",
    "ncbi.taxon.rank": "An organism's taxonomic rank, e.g. species or genus.",
    "gtdb.taxon.id": "GTDB genome-based taxonomy id for one organism.",
    "wikidata.qid": "Wikidata item id (Qxxxx) for one taxon — joins Wikidata/Wikipedia datasets.",
    "wikipedia.title": "English Wikipedia article title for one taxon — the pageviews join key.",
    # Molecular layer (uniprot_weaver hinge + hubs)
    "protein.query": "The text you start from — a gene symbol, protein name, or accession.",
    "protein.uniprot.accession": "UniProt accession for one protein — the main protein join key.",
    "gene.ncbi.id": "NCBI Gene id for one gene.",
    "gene.ensembl.id": "Ensembl gene id for one gene.",
    "gene.symbol": "A gene's official symbol, e.g. TP53 — joins gene databases.",
    "gene.hgnc.id": "HGNC id for one human gene.",
    "protein.ensembl.id": "Ensembl protein id for one protein.",
    "refseq.protein.id": "NCBI RefSeq protein accession (NP_/XP_) for one protein.",
    "nucleotide.insdc.accession": "INSDC nucleotide accession (GenBank/EMBL/DDBJ).",
    "go.term": "A Gene Ontology term id.",
    "enzyme.ec": "An Enzyme Commission (EC) number.",
    "chem.chebi.id": "A ChEBI chemical id.",
    "reaction.rhea.id": "A Rhea reaction id.",
    "pathway.reactome.id": "A Reactome pathway id.",
    "pathway.kegg.id": "A KEGG pathway id.",
    "protein.interpro.id": "An InterPro entry id.",
    "protein.pfam.id": "A Pfam family id.",
    "pdb.id": "A PDB / PDBe structure id.",
    "genome.accession": "NCBI genome assembly accession (GCF_/GCA_) — the genome join key.",
}


# Catalog of produced *leaf/payload* outputs that are NOT join keys (nothing
# consumes them) — descriptive fields a weaver emits. Unlike SHARED_KEYS this is a
# naming catalog, not a reachability gate: membership grants no join-eligibility,
# it just keeps output names consistent across weavers (so we don't drift between
# e.g. ``ncbi.taxon.parent_id`` and ``ncbi.parent_taxon_id``). To make a leaf output
# a real join target, *promote* it into SHARED_KEYS (a deliberate edit). See
# weaverkit/docs/decisions.md (Decision F).
OUTPUT_KEYS: dict[str, str] = {
    # wikidata_weaver / wikipedia_weaver leaf outputs
    "organism.vernacular_names": "Common (vernacular) names for one taxon, from Wikidata.",
    "wikipedia.pageviews": "Recent English-Wikipedia pageview count for one article — a popularity proxy.",
    # ncbi_weaver leaf outputs
    "ncbi.taxon.parent_id": "The parent taxon of this organism.",
    "ncbi.taxon.match_type": "How the name resolved to this taxid — exact, synonym, fuzzy, or taxid.",
    "ncbi.taxon.review_required": "Flag: the name match was ambiguous.",
    "ncbi.taxon.children_count": "How many child taxa this organism has at the requested rank.",
    "ncbi.taxon.children_records": "This organism's child taxa — taxid, name, rank.",
    # gtdb_weaver leaf output (gtdb.taxon.id is a shared join key — see SHARED_KEYS)
    "gtdb.lineage": "This organism's GTDB genome-based, rank-normalized lineage — "
    "an ordered list of {rank, name} from domain to species.",
    "gtdb.tree.rootpath": "This organism's path from the root of the GTDB reference tree "
    "to its species-representative leaf — an ordered list of [node_id, cumulative_depth]. "
    "Two paths give a patristic distance via their deepest shared node (gtdb_weaver.cophenetic).",
    # genome assembly outputs (ncbi_weaver list_genomes / describe_genome)
    "genome.assembly.count": "How many genome assemblies exist for this organism.",
    "genome.assembly.records": "Genome assemblies for this organism — accession, organism, level, RefSeq category.",
    "genome.assembly.title": "The name of one genome assembly.",
    "genome.assembly.level": "How complete one assembly is — Complete Genome, Chromosome, Scaffold, or Contig.",
    "genome.assembly.organism": "The source organism of one genome assembly.",
    "genome.assembly.detail": "Full detail of one assembly — submitter, dates, length/GC/N50, gene counts.",
    "genome.sequence.records": "The sequences in one genome — name, role, length, RefSeq/GenBank accession.",
    # NCBI gene outputs (ncbi_weaver resolve_gene / describe_gene / list_orthologs)
    # (gene.symbol is a shared join key — see SHARED_KEYS — consumed by uniprot map_to_accession)
    "gene.name": "The full name of this gene.",
    "gene.type": "What kind of gene this is — protein_coding, ncRNA, pseudo, …",
    "gene.organism": "The source organism of this gene.",
    "gene.detail": "Full record of this gene — symbol, description, type, chromosomes, synonyms, xrefs.",
    "gene.product.records": "The transcripts and proteins this gene makes — accessions and names.",
    "gene.ortholog.count": "How many orthologs this gene has across organisms.",
    "gene.ortholog.records": "This gene's orthologs — gene id, symbol, organism.",
    # microbe trait outputs (example_weaver / bacdive_weaver / future trait weavers)
    "microbe.trait.gram_stain": "This microbe's Gram stain — positive or negative.",
    "microbe.trait.optimum_temp": "The temperature this microbe grows best at.",
    "microbe.trait.metabolism": "How this microbe gets energy — aerobe, anaerobe, …",
    "microbe.trait.cell_shape": "This microbe's cell shape — rod, coccus, …",
    "microbe.trait.motility": "Whether this microbe can move.",
    "microbe.trait.spore_formation": "Whether this microbe forms spores.",
    "microbe.trait.oxygen_tolerance": "How this microbe relates to oxygen — aerobe, anaerobe, facultative, …",
    "microbe.trait.optimum_ph": "The pH this microbe grows best at.",
    # microbe ecological-function outputs (faprotax_weaver)
    "microbe.ecology.functional_groups": "FAPROTAX ecological/metabolic functional "
    "groups this microbe's clade is affiliated with (e.g. methanotrophy, nitrification, "
    "sulfate_respiration).",
    # microbe–disease association outputs (disbiome_weaver)
    "microbe.disease.names": "The diseases this microbe is linked to.",
    "microbe.disease.count": "How many disease-association experiments mention this microbe.",
    "microbe.disease.associations": "This microbe's disease links — disease, elevated/reduced, "
    "method, sample, host.",
    "microbe.disease.records": "Full Disbiome experiment rows linking this microbe to diseases.",
    # microbe abundance/ecology outputs (gmrepo_weaver) — measured from curated gut metagenomes
    "microbe.abundance.overview": "This microbe's global gut-metagenome abundance summary — "
    "percent of all samples it occurs in, its median relative abundance, and how many "
    "phenotypes it appears in (GMrepo).",
    "microbe.abundance.phenotype_names": "The gut-metagenome phenotypes (diseases/health) "
    "this microbe is reported prevalent in (GMrepo).",
    "microbe.abundance.count": "How many phenotypes this microbe has a GMrepo abundance record for.",
    "microbe.abundance.associations": "This microbe's per-phenotype abundance signal — mesh_id, "
    "phenotype, sample count, prevalence %, and median relative abundance (GMrepo).",
    "microbe.abundance.records": "Full GMrepo abundance rows for this microbe — the global "
    "overview plus every per-phenotype prevalence/abundance record.",
    # AGORA2 metabolic-reconstruction outputs (agora_weaver)
    "microbe.metabolism.reconstruction": "This organism's AGORA2 genome-scale metabolic "
    "reconstruction(s) — a list of {reconstruction_id, gcf_id} (the source RefSeq genome).",
    "microbe.metabolism.reactions": "The reaction repertoire of this organism's AGORA2 "
    "reconstruction(s) — a list of {reconstruction_id, abbreviation, subsystem, ec, kegg, rhea}.",
    # uniprot_weaver leaf outputs (descriptive protein-entry fields)
    "protein.name": "This protein's recommended name.",
    "protein.gene": "The gene that codes for this protein.",
    "protein.organism": "The organism this protein comes from.",
    "protein.function": "What this protein does — UniProt's curated summary.",
    "protein.length": "This protein's length in amino acids.",
    "protein.reviewed": "Whether this entry is reviewed (Swiss-Prot) or not (TrEMBL).",
    # UniProt ID-mapping outputs (uniprot_weaver map_to/from_accession)
    "protein.uniprot.mapping.count": "How many ids this protein mapped to.",
    "protein.uniprot.mapping.records": "The ids this protein mapped to — id plus reviewed/db.",
    "orthodb.group": "This protein's OrthoDB orthologous-group id.",
    "eggnog.group": "This protein's eggNOG orthologous-group id.",
    "chembl.id": "This protein's ChEMBL target id.",
    "drugbank.id": "This protein's DrugBank id.",
    "string.id": "This protein's STRING id.",
    # protein-protein interaction outputs (string_weaver)
    "protein.interaction.partners": "The proteins this protein interacts with.",
    "protein.interaction.count": "How many interaction partners this protein has.",
    "protein.interaction.records": "This protein's interactions — partner, combined score, "
    "per-channel subscores.",
    # Gene Ontology annotation outputs (quickgo_weaver), grouped by GO aspect
    "go.molecular_function": "The molecular functions this protein is annotated with.",
    "go.biological_process": "The biological processes this protein takes part in.",
    "go.cellular_component": "Where in the cell this protein acts.",
    "go.count": "How many GO terms annotate this protein.",
    "go.records": "This protein's GO annotations — GO id, name, aspect.",
    # one GO term's detail (quickgo_weaver describe_go_term — consumes go.term)
    "go.term.name": "The name of this GO term.",
    "go.term.aspect": "This GO term's aspect — molecular_function, biological_process, or cellular_component.",
    "go.term.definition": "What this GO term means.",
    "go.term.detail": "Full detail of this GO term — name, aspect, definition, synonyms.",
    # experimental-structure outputs (pdbe_weaver)
    "structure.pdb.ids": "Experimental PDB structures of this protein.",
    "structure.pdb.count": "How many PDB structures cover this protein.",
    "structure.pdb.records": "This protein's PDB structures — id, method, resolution, coverage.",
    # one PDB structure's detail (pdbe_weaver describe_structure — consumes pdb.id)
    "structure.pdb.title": "The title of one PDB structure.",
    "structure.pdb.method": "How one PDB structure was solved.",
    "structure.pdb.release_date": "When one PDB structure was released.",
    "structure.pdb.detail": "Full detail of one PDB structure — title, method, dates, authors.",
    # predicted-structure outputs (alphafold_weaver)
    "structure.alphafold.entry_id": "This protein's AlphaFold model id.",
    "structure.alphafold.mean_plddt": "The AlphaFold model's mean pLDDT confidence, 0–100.",
    "structure.alphafold.model_url": "Where to download this protein's AlphaFold model.",
    "structure.alphafold.pae_image_url": "The AlphaFold model's predicted-aligned-error plot.",
    "structure.alphafold.version": "Which AlphaFold model version this is.",
    "structure.alphafold.records": "Full AlphaFold model metadata — id, confidence, URLs.",
    # biological-pathway outputs (reactome_weaver)
    "pathway.reactome.names": "The Reactome pathways this protein takes part in.",
    "pathway.reactome.count": "How many Reactome pathways this protein is in.",
    "pathway.reactome.records": "This protein's Reactome pathways — stable id, name, in-disease flag.",
    # one Reactome pathway's detail (reactome_weaver describe_pathway — consumes pathway.reactome.id)
    "pathway.reactome.display_name": "The name of one Reactome pathway.",
    "pathway.reactome.species": "The species of one Reactome pathway.",
    "pathway.reactome.in_disease": "Whether one Reactome pathway is disease-associated.",
    "pathway.reactome.detail": "Full detail of one Reactome pathway — name, species, disease flag, type.",
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
