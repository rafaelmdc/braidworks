# Capability inventory and common interface assessment

Date: 2026-10-08; source revision `d5e7543`. This inventories current contracts,
not accepted feature proposals. Read each source report for actual backend semantics.

## Every declared capability

| Weaver/capability | Inputs | Groups and output keys | Backends | Parameters | Fan sets |
|---|---|---|---|---|---|
| [example](example.audit.md): describe_traits | ncbi.taxon.id | traits.core: microbe.trait.gram_stain<br>traits.growth: microbe.trait.optimum_temp | local | — | — |
| [uniprot](uniprot.audit.md): resolve_protein | protein.query | identity: protein.uniprot.accession, protein.name, protein.gene, protein.organism, protein.reviewed<br>taxonomy: ncbi.taxon.id<br>function: protein.function, protein.length | api | organism | — |
| [uniprot](uniprot.audit.md): map_to_accession | gene.ncbi.id, gene.ensembl.id, protein.ensembl.id, gene.symbol, refseq.protein.id, gene.hgnc.id, nucleotide.insdc.accession, pdb.id (alternatives) | mapping: protein.uniprot.accession, protein.uniprot.mapping.count, protein.uniprot.mapping.records | api | — | protein.uniprot.accession |
| [uniprot](uniprot.audit.md): map_from_accession | protein.uniprot.accession | mapping: gene.ncbi.id, gene.ensembl.id, protein.ensembl.id, pathway.kegg.id, pathway.reactome.id, refseq.protein.id, orthodb.group, eggnog.group, chembl.id, drugbank.id, pdb.id, string.id, protein.uniprot.mapping.count, protein.uniprot.mapping.records | api | — | gene.ncbi.id, gene.ensembl.id, protein.ensembl.id, pathway.kegg.id, pathway.reactome.id, refseq.protein.id, orthodb.group, eggnog.group, chembl.id, drugbank.id, pdb.id, string.id |
| [pdbe](pdbe.audit.md): list_structures | protein.uniprot.accession | summary: pdb.id, structure.pdb.ids, structure.pdb.count<br>full: structure.pdb.records | api | — | pdb.id |
| [pdbe](pdbe.audit.md): describe_structure | pdb.id | detail: structure.pdb.title, structure.pdb.method, structure.pdb.release_date, structure.pdb.detail | api | — | — |
| [alphafold](alphafold.audit.md): describe_model | protein.uniprot.accession | model: structure.alphafold.entry_id, structure.alphafold.mean_plddt, structure.alphafold.model_url, structure.alphafold.pae_image_url, structure.alphafold.version<br>full: structure.alphafold.records | api | — | — |
| [quickgo](quickgo.audit.md): list_go_terms | protein.uniprot.accession | aspects: go.molecular_function, go.biological_process, go.cellular_component<br>summary: go.term, go.count<br>full: go.records<br>annotations: go.annotation.records<br>coverage: go.annotation.coverage | api | — | go.term |
| [quickgo](quickgo.audit.md): describe_go_term | go.term | detail: go.term.name, go.term.aspect, go.term.definition, go.term.detail | api | — | — |
| [reactome](reactome.audit.md): list_pathways | protein.uniprot.accession | summary: pathway.reactome.id, pathway.reactome.names, pathway.reactome.count<br>full: pathway.reactome.records | api | — | pathway.reactome.id |
| [reactome](reactome.audit.md): describe_pathway | pathway.reactome.id | detail: pathway.reactome.display_name, pathway.reactome.species, pathway.reactome.in_disease, pathway.reactome.detail | api | — | — |
| [string](string.audit.md): list_interactions | protein.uniprot.accession | summary: protein.query, protein.interaction.partners, protein.interaction.count<br>full: protein.interaction.records | api | — | protein.query |
| [ncbi](ncbi.audit.md): ncbi.resolve_name | organism.name | core: ncbi.taxon.id, organism.scientific_name, ncbi.taxon.rank, ncbi.taxon.parent_id, ncbi.taxon.match_type, ncbi.taxon.review_required<br>lineage: ncbi.taxon.lineage, ncbi.taxon.species_id | local, api | — | — |
| [ncbi](ncbi.audit.md): ncbi.describe_taxon | ncbi.taxon.id | core: organism.scientific_name, ncbi.taxon.rank, ncbi.taxon.parent_id<br>lineage: ncbi.taxon.lineage, ncbi.taxon.species_id | local, api | — | — |
| [ncbi](ncbi.audit.md): ncbi.list_children | ncbi.taxon.id | children: ncbi.taxon.id, ncbi.taxon.children_count, ncbi.taxon.children_records | api | rank=species | ncbi.taxon.id |
| [ncbi](ncbi.audit.md): ncbi.list_genomes | ncbi.taxon.id | genomes: genome.accession, genome.assembly.count, genome.assembly.records | api | reference_only=False, annotated_only=False, assembly_level | genome.accession |
| [ncbi](ncbi.audit.md): ncbi.describe_genome | genome.accession | assembly: genome.assembly.title, genome.assembly.level, genome.assembly.organism, genome.assembly.detail<br>sequences: genome.sequence.records | api | — | — |
| [ncbi](ncbi.audit.md): ncbi.resolve_gene | protein.query | gene: gene.ncbi.id, gene.symbol, gene.name, gene.organism | api | taxon=9606 | — |
| [ncbi](ncbi.audit.md): ncbi.describe_gene | gene.ncbi.id | summary: gene.symbol, gene.name, gene.type, gene.organism, gene.detail<br>products: gene.product.records | api | — | — |
| [ncbi](ncbi.audit.md): ncbi.list_orthologs | gene.ncbi.id | orthologs: gene.ncbi.id, gene.ortholog.count, gene.ortholog.records | api | taxon_filter | gene.ncbi.id |
| [gtdb](gtdb.audit.md): describe_gtdb_taxonomy | ncbi.taxon.id, organism.scientific_name (alternatives) | core: gtdb.taxon.id<br>lineage: gtdb.lineage | local, api | — | — |
| [gtdb](gtdb.audit.md): describe_gtdb_tree_placement | ncbi.taxon.id, organism.scientific_name (alternatives) | core: gtdb.tree.rootpath | local | — | — |
| [bacdive](bacdive.audit.md): describe_traits | organism.scientific_name | morphology: microbe.trait.gram_stain, microbe.trait.cell_shape, microbe.trait.motility, microbe.trait.spore_formation<br>physiology: microbe.trait.oxygen_tolerance<br>growth: microbe.trait.optimum_temp, microbe.trait.optimum_ph | api | — | — |
| [agora](agora.audit.md): describe_metabolic_reconstruction | ncbi.taxon.id | core: microbe.metabolism.reconstruction<br>reactions: microbe.metabolism.reactions<br>model: microbe.metabolism.sbml | local | — | — |
| [faprotax](faprotax.audit.md): describe_ecology | ncbi.taxon.lineage | ecology: microbe.ecology.functional_groups | local | — | — |
| [disbiome](disbiome.audit.md): disbiome.list_diseases | ncbi.taxon.species_id | summary: microbe.disease.names, microbe.disease.count<br>associations: microbe.disease.associations<br>full: microbe.disease.records | local | — | — |
| [gmrepo](gmrepo.audit.md): gmrepo.list_abundances | ncbi.taxon.id | summary: microbe.abundance.overview, microbe.abundance.phenotype_names, microbe.abundance.count<br>associations: microbe.abundance.associations<br>full: microbe.abundance.records | local | — | — |
| [gmrepo](gmrepo.audit.md): gmrepo.sample_profiles | disease.mesh.id | profiles: microbe.abundance.sample_profiles | local | — | — |
| [mondo](mondo.audit.md): mondo.lookup_by_mesh | disease.mesh.id | term: disease.mondo.id, disease.ontology.name, disease.ontology.parents, disease.ontology.depth<br>ancestors: disease.ontology.ancestors | local | — | — |
| [mondo](mondo.audit.md): mondo.lookup_by_meddra | disease.meddra.id | term: disease.mondo.id, disease.ontology.name, disease.ontology.parents, disease.ontology.depth<br>ancestors: disease.ontology.ancestors | local | — | — |
| [mondo](mondo.audit.md): mondo.lookup_by_name | disease.name | term: disease.mondo.id, disease.ontology.name, disease.ontology.parents, disease.ontology.depth<br>ancestors: disease.ontology.ancestors | local | — | — |
| [wikidata](wikidata.audit.md): resolve_taxon | organism.scientific_name | core: wikidata.qid, wikipedia.title, wikidata.sitelinks<br>names: organism.vernacular_names | api | expected_rank | — |
| [wikipedia](wikipedia.audit.md): describe_pageviews | wikipedia.title | core: wikipedia.pageviews | api, local | — | — |

Inventory: **17 packages, 33 declared capabilities**. All three version sites
match for every package; all strict spec/manifest fixture gates passed.

## Responsibility map and scaffold comparison

Provider/discovery → configured or introspection factory → manifest/dispatch → backend
IO/storage → source projection/record → mapper → shared executor/interfaces.
The generic template-method dispatch already lives in core; weavers compose backend
strategies. Current classes are not uniformly missing patterns.

| Sources | Intentional difference from fresh scaffold | Boundary worth considering |
|---|---|---|
| Example/FAPROTAX | Real bundled-resource parser and immutable-data candidate | Pure parsing/evaluation; no storage repository needed |
| UniProt | Async job submit/poll/results and source-target dispatch | Composed mapping-job adapter + pure correlation |
| PDBe/Reactome/QuickGO/STRING/AlphaFold/Wikidata | Real endpoint selection/bulk/page/retry logic | Source-local validation/collection and projection; helpers first |
| NCBI | Custom TaxonMatch/review mapper, source dispatch and resolver service | Retain A08 runtime; operation protocols/composed domain adapters only |
| GTDB | Release crosswalk, Newick geometry and source-bound files | Coherent release descriptor + explicit crosswalk/geometry policies |
| AGORA | Bundled crosswalk, optional reaction DB/model artifacts | Model artifact service with explicit group availability |
| Disbiome/GMrepo/MONDO | Source-specific joins/graph queries and local builders | Coverage-bearing build/query helpers; no mandatory extra repository layer |
| Wikipedia | Streaming dump index plus temporal API measure | One effective measurement descriptor and pure window/bin reduction |

All 16 scaffolded-source specs were rendered **in memory only** using current
`generate_files` and compared with existing Python artifacts. Differences include
implemented backend/fixture/factory and contract examples; difference counts are not
defect counts. Scratch comparison `.audit-local/weaver-scaffold-comparison.json`.
NCBI handwritten vocabulary was neither regenerated nor overwritten. Example was
also written into a scratch destination to establish actual force-overwrite behavior.

## Python, CLI and browser usability

| Surface | Verified scope | Limitations/recommendation |
|---|---|---|
| Python | All package fixtures execute through cwd-correct suites; factories/config inspected individually | Construction-only examples common; real async execution/group/error/review examples proposed per source |
| CLI | Entry-point metadata, capability/params and source setup catalogue inspected |16real sources discoverable; Example intentionally manual. Custom paths/clients belong to Python builders; default-cache prerequisites explicit |
| Browser | Source code uses same discovered registry, query preparation/executor; exposes declared params, output choices, backend policy and batch inputs | No per-source live browser session/click test performed. Discovery does not acquire missing DBs; upstream/output semantics remain backend responsibility |

[Serve preparation](../../../weaverkit/src/weaverkit/serve.py) uses QueryRequest,
effective capability parameters and backend/expansion/review policies.
[View/discovery](../../../weaverkit/src/weaverkit/view.py) exposes shared keys,
leaf outputs and parameter declarations. [Setup catalogue](../../sources.md) records
default-cache requirements; STRING parameter advice there is currently ahead of its
parameterless manifest and belongs with WV-STRING-005/007. A common interface cannot
expose source knobs absent from specs. Do not add arbitrary constructor details to
human query forms merely to repair ignored configuration.

The GUI machinery already passed earlier programme tests; this audit does not claim
fresh end-to-end browser validation for all sources. Bounded offline fixture query
checks establish backend contracts, not full current upstream-service certification.
CLI/GUI code generation should be exercised for accepted new key/parameter changes.

## Evidence, priority and decision conventions

Every report identifies finding ID, priority/confidence, inspected paths or probes,
impact and recommended boundary. Matching specs supply acceptance criteria and
compatibility; plans supply ordered work packages/checks. All decisions **proposed**.
P0: local data destruction; P1: major incorrect/blocked behavior; P2: worthwhile
correctness/maintenance/workflow improvements; P3: optional/profiling-driven work.
Features remain conditional even where ranked P2. Confidence refers to the precise
code/probe claim, not frequency in real scientific datasets.

[Summary](summary.md), [index](README.md), [full findings register](findings.tsv).
