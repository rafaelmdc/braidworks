#!/usr/bin/env bash
#
# Braidworks pre-1.0 stress braids — 10 "annoying" real-world integrations.
#
# These are deliberately the hard cases: cross-hub bridges, one->many fan-out,
# self-loop traversal (gene->genes, protein->proteins, taxon->taxa), nested fans,
# OR-consume routing, batch x traversal, and the widest single-root plans. Each
# braid maps to a real integration motif from the literature (cited inline).
#
# Purpose: shake out planner/cardinality/re-root bugs before 1.0. Everything hits
# live, mostly keyless public APIs (ncbi key is optional). Expect some braids to
# be slow or to surface upstream hiccups — that's the point.
#
# Run start-to-finish:  bash docs/testing-examples.sh
# Run one braid:        bash docs/testing-examples.sh 3
# Network recap:        bash docs/testing-examples.sh weavers
#
# Two hubs, three bridges:
#   taxonomy/microbiome hub  keyed on ncbi.taxon.id / organism.scientific_name
#   molecular hub            keyed on protein.uniprot.accession
#   gene sub-hub             keyed on gene.ncbi.id
#   bridges: uniprot.resolve_protein also emits ncbi.taxon.id (molecular->taxonomy);
#            map_to_accession: gene.ncbi.id->accession; ncbi.resolve_gene: query->gene.

set -u
BW="braidworks"   # or: alias bw='uv run --all-packages braidworks'

run() {   # run <n> <title> <cmd...>
  local n="$1" title="$2"; shift 2
  printf '\n\033[1;36m== Braid %s — %s ==\033[0m\n' "$n" "$title"
  printf '\033[2m$ %s\033[0m\n' "$*"
  "$@"
  printf '\033[2m[braid %s exit=%s]\033[0m\n' "$n" "$?"
}

want="${1:-all}"
[ "$want" = weavers ] && { $BW weavers; exit 0; }

# 1. Disease dossier for a named bug — the cross-hub bridge test.
#    Nat Microbiol 2022 (s41564-022-01121-z): disease-associated signature species.
#    Input is a protein.query, not a taxid: planner must use uniprot.resolve_protein
#    PURELY for its ncbi.taxon.id side-output to reach disbiome. Two producers of
#    ncbi.taxon.id (ncbi.resolve_name vs uniprot) -> cheapest-pick must fire.
[ "$want" = all -o "$want" = 1 ] && run 1 "cross-hub bridge: protein name -> disease" \
  $BW weave --have protein.query="Akkermansia muciniphila" \
    --want microbe.disease.associations,microbe.trait.oxygen_tolerance

# 2. Genus-wide trait+disease sweep — wide fan-out then double annotate.
#    Functional-redundancy motif. list_children fans taxon->taxa, then TWO independent
#    annotation subplans (traits + diseases) re-root on each child.
[ "$want" = all -o "$want" = 2 ] && run 2 "wide fan + double annotate per child" \
  $BW weave --have organism.name="Bacteroides" \
    --traverse ncbi.list_children \
    --want organism.scientific_name,microbe.trait.gram_stain,microbe.disease.count \
    --expand top:5

# 3. Ortholog conservation of function — self-loop + per-node cross-hub annotate.
#    StructSeq2GO motif: orthology-based function transfer. The gnarliest path:
#    resolve_gene -> list_orthologs (self-loop fan) -> per ortholog map_to_accession
#    (gene->uniprot bridge) -> quickgo + reactome (each fans further). Nested fan.
[ "$want" = all -o "$want" = 3 ] && run 3 "ortholog self-loop -> cross-hub GO/pathway" \
  $BW weave --have protein.query="TP53" \
    --traverse ncbi.list_orthologs \
    --want go.biological_process,pathway.reactome.names \
    --expand top:5

# 4. STRING neighborhood, annotated — protein->protein self-loop.
#    MSNGO network-propagation motif. list_interactions emits protein.query for each
#    partner; every partner re-roots back through uniprot.resolve_protein -> N replans.
[ "$want" = all -o "$want" = 4 ] && run 4 "STRING partner self-loop -> per-partner pathways" \
  $BW weave --have protein.query="BRCA1" \
    --traverse string.list_interactions \
    --want protein.name,pathway.reactome.names --expand top:10

# 5. Full structural-biology card — heterogeneous fan on one accession.
#    PNAS 2023 structure-aware annotation. One accession fanning into FOUR producers,
#    one (list_structures) itself a one->many fan. Combinatorial want-set, no traversal.
[ "$want" = all -o "$want" = 5 ] && run 5 "one accession -> four structural producers" \
  $BW weave --have protein.query="ACE2 human" \
    --want structure.pdb.records,structure.alphafold.mean_plddt,structure.alphafold.pae_image_url,go.cellular_component

# 6. xref explosion — the one->many HETEROGENEOUS output.
#    neXtProt cross-reference integration. map_from_accession emits ~13 distinct xref
#    TYPES from one accession; does record-shaping keep them aligned per accession?
[ "$want" = all -o "$want" = 6 ] && run 6 "heterogeneous xref fan from one accession" \
  $BW weave --have protein.query="EGFR human" \
    --want pathway.kegg.id,chembl.id,drugbank.id,pdb.id,orthodb.group,string.id

# 7. OR-consume routing — feed it the "wrong" id type.
#    Tests consumes_any directly. map_to_accession accepts 8 input id types; hand it a
#    PDB id (also consumed by pdbe.describe_structure -> decoy edge) and round-trip.
[ "$want" = all -o "$want" = 7 ] && run 7 "OR-consume: pdb.id -> accession -> GO/structure" \
  $BW weave --have pdb.id=6M0J \
    --want go.molecular_function,structure.alphafold.model_url

# 8. Deep taxonomy -> genome drill — multi-hop fan then describe.
#    Comparative-genomics motif. resolve_name -> list_genomes (fan) -> describe_genome.
[ "$want" = all -o "$want" = 8 ] && run 8 "name -> genomes (fan) -> describe each" \
  $BW weave --have organism.name="Mycobacterium tuberculosis" \
    --traverse ncbi.list_genomes \
    --want genome.assembly.title,genome.assembly.level,genome.assembly.organism \
    --expand top:8

# 9. Batch microbiome panel — fan-out ON TOP OF batch input.
#    Disease-signature panels. N input rows x M children each x disease subplan:
#    broadcast + fan + re-root all interacting. Most likely to mis-attribute rows.
[ "$want" = all -o "$want" = 9 ] && run 9 "batch x traversal x fan (worst-case cardinality)" \
  bash -c 'printf "Fusobacterium nucleatum\nClostridioides difficile\nHelicobacter pylori\n" \
    | '"$BW"' weave --in-file - --in-type organism.name \
        --traverse ncbi.list_children \
        --want organism.scientific_name,microbe.disease.names --expand all'

# 10. "What does this gene DO?" — every endpoint at once, max width.
#     PIPA consensus-annotation motif. 8 wants spanning 6 weavers off one accession,
#     several of them fans. Widest single-root plan; surfaces duplicate-work/ordering.
[ "$want" = all -o "$want" = 10 ] && run 10 "widest single-root: 8 wants, 6 weavers" \
  $BW weave --have protein.query="MTOR" \
    --want protein.function,go.biological_process,go.molecular_function,pathway.reactome.names,structure.pdb.count,structure.alphafold.mean_plddt,protein.interaction.count,drugbank.id

printf '\n\033[1;32mdone.\033[0m\n'

# ===========================================================================
# FINDINGS — first run 2026-06-17 (6/10 clean), after fixes (10/10 clean).
# ===========================================================================
#
# BUG 1 [FIXED] (had blocked braids 2,3,4,8,9 — the headline pre-1.0 issue):
#   --traverse / --for-each did NOT plan a resolution PRELUDE — it required --have to
#   ALREADY be the fan's consume type, so natural input (organism.name, protein.query)
#   was rejected with "missing required input: ncbi.taxon.id / gene.ncbi.id / accession".
#   Fix (core/traverse.py): before each fan, if the fan's input isn't in hand, plan+run
#   a resolution prelude (have -> fan.consume), same as plain `weave` does. CRITICAL
#   follow-on: the prelude's BYPRODUCT strands (resolve_name also emits the seed's
#   organism.scientific_name) were riding into the fanned children and stale-filling
#   them (every child reported as the parent). Fixed with StrandSet.restricted_to({src}):
#   feed the fan only the bare join key. Regression tests in core/tests/test_traverse.py.
#
# BUG 2 [FIXED] (braid 4): --traverse rejected the qualified id for bare-id weavers
#   ('string.list_interactions') though --help promises that form and it worked for
#   ncbi.* (whose cap ids are already namespaced). Fix: resolve_traversal also matches
#   token == f"{weaver}.{capability}". Test: test_resolve_qualified_id_for_bare_capability.
#
# SMELL 4 [NOT A BUG] (braid 7): pdb 6M0J -> accession P0DTC2 -> alphafold yields
#   AF-0000000365840314-model_v1.pdb. Confirmed via curl: the LIVE AlphaFold API returns
#   exactly that for P0DTC2 (its synthetic id for the SARS-CoV-2 reference proteome).
#   Braidworks passes the real pdbUrl through faithfully — correct behavior, no fix.
#
# SMELL 5 [KNOWN GAP, not hacked] (braid 1): the bridge uniprot.resolve_protein(
#   "Akkermansia muciniphila") returns taxid 349741 = the STRAIN (ATCC BAA-835), but
#   disbiome is SPECIES-keyed (239935, which has T2D/UC/Crohn's/Parkinson's...). disbiome
#   correctly returns *unresolved* for the strain. Two real items, both features not bugs:
#   (a) taxonomy normalization — climb a strain taxid to its species rank before a
#       species-keyed lookup; (b) routing — two producers of ncbi.taxon.id, and the
#   cheapest pick (uniprot=strain) is wrong-granularity here vs ncbi.resolve_name=species.
#   Workaround today: resolve the taxid via ncbi.resolve_name, or pass the species taxid.
#
# FOOTGUN 6 [KNOWN, by design] (braid 10): "MTOR" w/o --param organism=9606 resolves to
#   Drosophila Megator, not human MTOR kinase. Pin the species (see demo.sh).
#
# CLEAN WINS: braids 5 (4-way structural fan), 6 (heterogeneous xref fan, all 6 aligned),
#   7 (OR-consume routed correctly), 10 (7-step widest plan). After the fixes all 10 exit 0
#   and the formerly-broken fans return distinct, biologically-correct children.
# ===========================================================================
