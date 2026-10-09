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

## Building or replacing the local database

```bash
ncbi-weaver build-db --dump taxdump.tar.gz --db data/ncbi_taxonomy.sqlite \
    --report-json build-report.json
```

Both `build-db` and Python's `build_taxonomy_database()` build in a temporary directory
beside the target, validate the result, then replace the target atomically. A failed
parse or validation preserves the existing database; temporary build files are cleaned
up. Builds for the same target use the existing cross-process build lock. Allow disk
space for the complete replacement alongside the old database, and close writable
SQLite connections before replacing it. A successful replacement contains only the new
reference database, so keep application-owned tables in a separate database.

The human summary and optional JSON report include counts, validation checks and the
source archive SHA-256. Invalid archives exit with status 1 and an error message.

## Choosing a backend

```python
from ncbi_weaver import build_ncbi_weaver

weaver = build_ncbi_weaver(enable_api=True)                  # API only — no local data, zero setup
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite")  # local only — prebuilt SQLite
weaver = build_ncbi_weaver(auto_setup=True)                 # build/reuse the DB in the per-user cache
weaver = build_ncbi_weaver(db_path="…", enable_api=True)    # local preferred, API fallback
```

The manifest advertises only the backends you wire in, so a missing one never breaks
planning — it just isn't an option. See [docs/database.md](https://github.com/rafaelmdc/braidworks/blob/main/docs/database.md) for the
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

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/ncbi_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/ncbi_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

Taxonomy, genome, gene and requested enrichment responses are validated at source-local seams. Taxonomy, assembly/gene-detail and symbol request chunks preserve unrelated successes. Taxonomy HTTP 400/404 and explicitly reported invalid-identifier absence remain misses; network/service/malformed data failures are errors. The observed empty taxonomy-suggest response {} remains a miss. Failed requested lineage, sequence or product enrichment now makes the affected query an error instead of returning apparent success with silently missing requested fields. Cancellation and unrelated programming faults propagate through enrichment. API-only live checks select test_live tests; the unrestricted test-live target also acquires the large local taxonomy database.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Report coverage

API report traversals reject repeated page tokens and stop at a positive
`max_report_pages` budget (default 1,000 pages per traversal). An interrupted
traversal returns `ERROR` with its observed page count and incomplete scope,
claims no completed groups and is not cached. Products now follow pagination;
product and sequence records no longer silently stop at 200. Their `.coverage`
outputs report the returned/observed record counts and successful report completion.
List capabilities retain their 200-row display cap with uncapped identifier sets
and true distinct counts, after every source page has been acquired.

## Bounded API batches

Exact taxonomy, gene-symbol and entity-summary lookups retain their chunked bulk
requests. Children, genome lists, ortholog lists, fuzzy fallbacks and requested
sequence/product enrichment use at most four workers per batch by default.
Duplicate identifiers share source work within the batch, and returned records
retain their original input positions and queries. Cancellation joins the workers
before returning; expected upstream failures remain per-input error values.

Configure `build_ncbi_weaver(enable_api=True, api_max_concurrency=2)` or
`DatasetsV2Backend(max_concurrency=2)` to change the positive integer worker limit.
Pagination remains sequential within each identifier and is bounded separately by
`max_report_pages`. All requests pass through the pacing hook: its default is five
requests per second, following the [NCBI Datasets default limit](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/api/api-keys/).
An executor request budget or `BRAIDWORKS_RATE_LIMITS=ncbi:api=...` overrides that
default. Concurrency is not a requests-per-second limit.

When one gene symbol echoes multiple distinct gene reports, the API returns an
error with sorted candidate evidence for review instead of selecting the first.
Fuzzy taxonomy suggestions are deduplicated by taxon ID and ordered by score,
then taxon ID/name/rank; ambiguous suggestions retain their review requirement.
