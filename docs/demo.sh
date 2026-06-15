#!/usr/bin/env bash
#
# Braidworks live demo — one gene name, the whole molecular picture.
#
# The story (for a bench biologist): you know a gene by name. Normally, assembling
# its protein's structures, interactions, pathways and functions means visiting five
# or six websites (or writing a day of glue code against five different APIs). With
# Braidworks you say what you HAVE (a gene name) and what you WANT, and it finds the
# route across every database for you — in one command.
#
# Run it line by line in front of an audience, or `bash docs/demo.sh` start to finish.
# Data prints to stdout; the resolved/unresolved count prints to stderr.
#
# Prereqs: the weavers installed (from the repo root: `uv run --all-packages braidworks
# weavers` lists them). Everything below hits live, keyless public APIs — no API key.

set -u
BW="braidworks"   # or: alias bw='uv run --all-packages braidworks'

# ---------------------------------------------------------------------------
# Act 0 — what's in the network?
# ---------------------------------------------------------------------------
# Each weaver wraps one database as a typed transformation (consumes -> produces).
# The planner stitches them into a route. See the whole network offline: `make view`.
$BW weavers
$BW path --from protein.query --to pathway.reactome.names   # preview a route, no network

# ---------------------------------------------------------------------------
# Act 1 — the dossier: one gene name -> SIX databases, one command
# ---------------------------------------------------------------------------
# protein.query=TP53 is resolved by UniProt to the human protein (P04637); that one
# accession is the hub every molecular database hangs off. --param organism=9606 pins
# the species (a bare "TP53" otherwise resolves to whichever species ranks first).
#
#   UniProt   -> name, organism            PDBe      -> # experimental structures
#   AlphaFold -> predicted-model URL       STRING    -> # interaction partners
#   Reactome  -> # pathways                QuickGO   -> # GO terms
$BW weave --have protein.query=TP53 --param organism=9606 \
    --want protein.name,protein.organism,structure.pdb.count,\
structure.alphafold.model_url,protein.interaction.count,pathway.reactome.count,go.count \
    --format human

# ---------------------------------------------------------------------------
# Act 2 — FAN-OUT: TP53 has 312 structures; describe the most recent five
# ---------------------------------------------------------------------------
# PDBe returns a *set* of structure ids. `--expand top:5` forks the weave into one
# child per structure and describes each — title, method, release date. (`--expand all`
# would do every structure.) One input fans into many rows, each independently resolved.
$BW weave --have protein.query=TP53 --param organism=9606 \
    --want structure.pdb.title,structure.pdb.method,structure.pdb.release_date \
    --expand top:5 --format tsv

# ---------------------------------------------------------------------------
# Act 3 — FOR-EACH: walk TP53's orthologs across the primates, describe each
# ---------------------------------------------------------------------------
# `list_orthologs` returns more genes of the SAME type it consumed, so the planner
# can't auto-route it. `--for-each orthologs` fans THROUGH that relationship and then
# plans --want from each ortholog. 7157 = human TP53; taxon_filter=9443 = primates.
# Each row is one species' TP53 (the `from` column regroups them to the query).
$BW weave --have gene.ncbi.id=7157 --for-each orthologs --param taxon_filter=9443 \
    --want gene.symbol,gene.organism --format tsv

# ---------------------------------------------------------------------------
# Closing — it's bash all the way down
# ---------------------------------------------------------------------------
# Data is clean on stdout, so it pipes straight into jq / pandas / a spreadsheet:
#
#   $BW weave --have protein.query=TP53 --param organism=9606 \
#       --want pathway.reactome.names --format json | jq -r '.[].values'
#
# And the network is an offline, shareable HTML map: `make view && open docs/braidworks-network.html`
echo "done — say what you have, say what you want, get the route."
