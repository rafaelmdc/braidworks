# NCBI source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

<!-- weaverkit:capabilities:start -->
| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `ncbi.resolve_name` | `organism.name` | `core`, `lineage` | `local`, `api` | — |
| `ncbi.describe_taxon` | `ncbi.taxon.id` | `core`, `lineage` | `local`, `api` | — |
| `ncbi.describe_taxon_history` | `ncbi.taxon.id` | `history` | `local` | — |
| `ncbi.list_children` | `ncbi.taxon.id` | `children`; expands `ncbi.taxon.id` | `local`, `api` | `rank` |
| `ncbi.list_genomes` | `ncbi.taxon.id` | `genomes`; expands `genome.accession` | `api` | `reference_only`, `annotated_only`, `assembly_level` |
| `ncbi.describe_genome` | `genome.accession` | `assembly`, `sequences` | `api` | — |
| `ncbi.resolve_gene` | `protein.query` | `gene` | `api` | `taxon` |
| `ncbi.describe_gene` | `gene.ncbi.id` | `summary`, `products` | `api` | — |
| `ncbi.list_orthologs` | `gene.ncbi.id` | `orthologs`; expands `gene.ncbi.id` | `api` | `taxon_filter` |
<!-- weaverkit:capabilities:end -->

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

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

## Develop
Run the commands from this package directory.

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live NCBI Datasets API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/ncbi_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

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

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Backend responsibilities and JSON intermediates

`TaxonMatch`, `CandidateMatch` and `LineageEntry` in `ncbi_weaver.intermediate` each
support `to_json()` / `from_json()` with nested lineages/candidates and enum statuses.
Use `json.dumps(match.to_json())` for wire JSON; reconstruction produces detached records.

Backend interfaces are structural protocols, not a base class that every backend must
inherit. `ResolutionBackend` describes taxonomy resolution plus configuration/fingerprint;
`TaxonomyChildrenBackend`, `GenomeBackend` and `GeneBackend` describe their separate
operations. The local backend supplies taxonomy resolution, history, and descendant listing;
Datasets supplies taxonomy/children, genome, and gene operations.
Dispatch raises `UnsupportedCapability` when an optional operation is absent. Custom
backends should implement only their supported interfaces; existing duck-typed backends
continue to work. The previous ABC's inherited unsupported methods have been removed.

`ncbi.describe_taxon_history` is a **local-only** capability consuming
`ncbi.taxon.id` and producing `ncbi.taxon.history`. It reports requested/current
taxids, observed merge chains, current/merged/deleted/unknown status, history-file
availability and dump/build identity. New builds retain optional `merged.dmp` and
`delnodes.dmp`; missing files or older databases mean history unavailable, not
proof that an ID was never present. Deleted/unknown IDs have no inferred successor.
Existing `ncbi.describe_taxon` and name resolution are unchanged.

The history operation is separate from taxonomy resolution and advertised only
when local is wired. `ncbi.list_children` supports both local and API backends,
with the descendant/rank semantics described below.
No full taxonomy download is required for conformance: tiny synthetic dump
fixtures exercise merge chains, deletion, missing history and atomic failures.

Local `ncbi.list_children` traverses **all strict descendants**, not only direct
children. `rank=species` is the default; an empty rank returns every descendant
rank. The queried node is excluded, the fan key contains the full distinct sorted
ID set, and display records are capped at 200, matching the API. It reads only the current dump;
historical IDs are not silently followed. Empty/unknown subtrees are NO_MATCH.
Traversal uses the parent index off the event loop and terminates on cyclic input.

## Disabled backends

A local-only instance keeps taxonomy operations, including `ncbi.list_children`,
available locally. Gene and genome operations require the API backend. Their support
metadata remains available through `declared_manifest()` so planning reports the missing
API backend. This hook neither creates an API client nor downloads local data.
