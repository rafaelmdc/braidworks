# ncbi_weaver

NCBI Taxonomy — resolve a free-text organism name to its NCBI taxid + ranked lineage, and
describe a taxid. The **organism hub** of Braidworks (the taxid that BacDive, Disbiome,
STRING, and UniProt all join on) and the **advanced reference weaver**: a `resolver` (fuzzy
name matching, with review for ambiguous hits) with two interchangeable backends — a local
SQLite resolver (`taxonomy_resolver`, migrated from taxonbridge) and the NCBI Datasets v2
REST API. Both normalize to a neutral `TaxonMatch`, then one mapper produces strands, so the
backends emit identical shapes even though their matching differs.

- **Source:** https://www.ncbi.nlm.nih.gov/taxonomy · **License:** Public Domain — NCBI Taxonomy
- **Backends:** `local` (SQLite, bulk) + `api` (NCBI Datasets v2, keyless) · **Discoverable as** `ncbi`

## Capabilities

| Capability | Consumes | Produces (by group) |
|---|---|---|
| `ncbi.resolve_name` | `organism.name` | **core:** `ncbi.taxon.id`, `organism.scientific_name`, `ncbi.taxon.rank`, `ncbi.taxon.parent_id`, `ncbi.taxon.match_type`, `ncbi.taxon.review_required` · **lineage:** `ncbi.taxon.lineage` |
| `ncbi.describe_taxon` | `ncbi.taxon.id` | **core:** `organism.scientific_name`, `ncbi.taxon.rank`, `ncbi.taxon.parent_id` · **lineage:** `ncbi.taxon.lineage` |
| `ncbi.list_children` ⤜ | `ncbi.taxon.id` | **`ncbi.taxon.id`** (⤜ fan: each descendant), `ncbi.taxon.children_count`, `ncbi.taxon.children_records` — param `rank` (default `species`) · **api-only** |
| `ncbi.list_genomes` ⤜ | `ncbi.taxon.id` | **`genome.accession`** (⤜ fan: each assembly), `genome.assembly.count`, `genome.assembly.records` — params `reference_only`, `annotated_only`, `assembly_level` · **api-only** |
| `ncbi.describe_genome` | `genome.accession` | **assembly:** `genome.assembly.title`, `genome.assembly.level`, `genome.assembly.organism`, `genome.assembly.detail` · **sequences:** `genome.sequence.records` · **api-only** |
| `ncbi.resolve_gene` | `protein.query` | `gene.ncbi.id`, `gene.symbol`, `gene.name`, `gene.organism` — param `taxon` (default `9606`) · **api-only** |
| `ncbi.describe_gene` | `gene.ncbi.id` | **summary:** `gene.symbol`, `gene.name`, `gene.type`, `gene.organism`, `gene.detail` · **products:** `gene.product.records` · **api-only** |
| `ncbi.list_orthologs` ⤜ | `gene.ncbi.id` | **`gene.ncbi.id`** (⤜ fan: each ortholog), `gene.ortholog.count`, `gene.ortholog.records` — param `taxon_filter` · **api-only** |

This is a **resolver**: a fuzzy/ambiguous name match can come back flagged
(`ncbi.taxon.review_required`) for human confirmation rather than guessing silently.
The `list_*` capabilities emit a **set output** (the fan dimension) — `list_children`
fans a genus into its species, `list_genomes` fans an organism into its genome
assemblies (the new `genome.accession` join key bridges organism → genome):

`resolve_gene` consumes `protein.query` (a gene symbol is a valid molecular query), so a
query can take **two paths** from the same entry — UniProt's protein identity *or* the
NCBI gene id — and from there into structures, pathways, or orthologs.

```bash
braidworks run ncbi ncbi.list_children --have ncbi.taxon.id=216851 --param rank=species
braidworks run ncbi ncbi.list_genomes --have ncbi.taxon.id=562 --param reference_only=true
# organism -> each reference genome -> its assembly detail:
braidworks weave --have organism.name="Escherichia coli" \
    --want genome.assembly.level --param reference_only=true --expand all
# gene symbol -> NCBI gene id -> its mammalian orthologs, each drillable:
braidworks run ncbi ncbi.resolve_gene --have protein.query=TP53
braidworks run ncbi ncbi.list_orthologs --have gene.ncbi.id=7157 --param taxon_filter=40674
```

## Choosing a backend

```python
from ncbi_weaver import build_ncbi_weaver

weaver = build_ncbi_weaver(enable_api=True)                  # API only — no local data, zero setup
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite")  # local only — prebuilt SQLite
weaver = build_ncbi_weaver(auto_setup=True)                 # build/reuse the DB in the per-user cache
weaver = build_ncbi_weaver(db_path="…", enable_api=True)    # local preferred, API fallback
```

The manifest advertises only the backends you wire in, so a missing one never breaks
planning — it just isn't an option. See [docs/database.md](../../docs/database.md) for the
local DB. In an app that wires a `WeaverFactory`, `ncbi_weaver.register(factory)` adds it.

## Use it

The local backend needs a one-time DB (the `api` backend doesn't):

```bash
ncbi-weaver ensure                 # prompt, then download + build the SQLite into the user cache
ncbi-weaver ensure --yes           # non-interactive (CI/servers)

braidworks run ncbi ncbi.resolve_name --have organism.name="Homo sapiens"
braidworks weave --have organism.name="Escherichia coli" --want ncbi.taxon.id,ncbi.taxon.lineage
```

> `ncbi_weaver` is the hand-written "bring your own plumbing" reference — unlike scaffolded
> weavers it carries its own `dispatch.py`/`mapper.py`, the `taxonomy_resolver` library, and
> the `ncbi-weaver` CLI, so its `vocab.py` is **hand-maintained** (don't regenerate it).

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live NCBI Datasets API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](../../AGENTS.md).
