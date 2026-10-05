# Usage

Install → register weavers → plan → run. Most weavers are keyless public APIs and
need no setup; the taxonomy weaver additionally offers a local DB backend (covered
last).

## Install

Follow [installation.md](installation.md) for a minimal molecular environment,
the full workspace, or built wheels. In a selected workspace environment, activate
.venv/bin/activate before using the bare commands below, or prefix them with
uv run --no-sync. See [sources.md](sources.md) for local database prerequisites.

For the core 0.12 ambiguity/review defaults and explicit automatic-selection options,
see [migrating-to-0.12.md](migrating-to-0.12.md).

## From the command line (`braidworks`)

The fastest way in — no Python needed. The `braidworks` command (installed with
`braidworks-core`) discovers every installed weaver from entry points.

```bash
# plan a route from what you HAVE to what you WANT, and run it
braidworks weave --have protein.query=P04637 --want protein.name,structure.pdb.ids

# a whole column of IDs (one per line) -> a TSV for your spreadsheet
braidworks weave --in-file accessions.txt --in-type protein.query \
    --want protein.name,protein.gene --format tsv > out.tsv

# pipe from stdin straight into jq
cat accessions.txt | braidworks weave --in-file - --in-type protein.query \
    --want structure.pdb.ids --format jsonl | jq .

# fan one protein out into each of its structures, each then described
braidworks weave --have protein.query=P04637 \
    --want structure.pdb.title,structure.pdb.method --expand all --format tsv

# fan THROUGH a relationship: describe each of a gene's orthologs (TP53 -> primates)
braidworks weave --have gene.ncbi.id=7157 --for-each orthologs \
    --param taxon_filter=9443 --want gene.symbol,gene.organism --format tsv

# call one capability directly (no routing)
braidworks run pdbe describe_structure --have pdb.id=1tup

# inspect: what's installed, what flows where, and a route preview
braidworks weavers
braidworks keys --produces structure.pdb.ids
braidworks path --from protein.query --to pathway.reactome.id
braidworks references
```

Input comes from `--have TYPE=VALUE` (repeatable; broadcast onto every file row), a
file (`--in-file`; a CSV/TSV whose header is type-ids, or one value per line with
`--in-type`), or stdin (`--in-file -`). Output is `--format human|json|jsonl|tsv|csv`;
`--expand none|all|top:K` controls fan-out; `--param name=value` passes a capability's
filters/options (run `braidworks weavers` to see what each accepts; use
`capability:name=value` to target one step); `--only weaver,weaver` restricts the set.
`--for-each <relationship>` fans the weave *through* a list capability and then plans
`--want` from each result — use it when a relationship returns the **same** id type it
consumes (e.g. `orthologs`: gene → genes), which the planner can't auto-route; it
implies `--expand all`. `--traverse <capability-id>` is the explicit form for an
ambiguous or unnamed relationship.
Data goes to **stdout**, progress + a resolved/unresolved/review count to **stderr**,
so pipes stay clean. Exit code is non-zero only on a *fatal* structural error (a
`NO_MATCH` is valid data) — add `--strict` to also fail on any unresolved/review input.

Header-based stdin accepts CSV or TSV, detecting the delimiter from the type-ID
header. Inputs are read once, including traversal runs. Constants supplied with
`--have` are merged into each file row; row values override constants for the same key.
Sparse tables are grouped by the input types actually present in each row, so a
row containing a query can resolve first while another row starts from an accession.
Matching rows still execute in batches. Ordinary `weave` validates each group's
route before starting backend calls; a group with no route fails planning.

Parameter names, scopes and values are checked before execution. A scoped
`--param CAPABILITY:NAME=VALUE` must target a capability in the planned route.
Traversal includes resolver-prelude steps in this check, so an organism filter can
reach the step that resolves a name before fanning out. Python `fetch`/
`async_fetch` reject unknown names, unused scopes and mixed bare/scoped mappings.
Their `FetchResult` supports `to_json()` / `from_json()` for saving values, coverage,
references and error diagnostics.

Direct `run` preserves `resolved`, `unresolved`, `review` and `error` outcomes.
Backend errors always exit nonzero and report diagnostics on stderr. JSON/JSONL
retain error messages and ambiguous candidates; `--strict` additionally fails on
no-match and review outcomes. An unknown or unconfigured backend reports an error
without a traceback.

Machine exports (`json`, `jsonl`, `csv`, `tsv`) include one record per terminal
entity or fan-out leaf, including fatal `error` outcomes. `source_row` is the
one-based ordinal of an accepted input row (comments and blank lines are skipped);
it survives fan-out even when input labels repeat. `outcome` is unique within the
output, and `entity`/`parent` retain their human-readable labels. Records are ordered
by source row, keeping sibling order. Neither identifier is a persistent database ID.

Every record carries `status`, `missing` requested types, `requires_review`, warnings,
errors, structured diagnostics, completion steps and review candidates. `strands`
contains the exported values with confidence, provenance and metadata. `references`
is the run's bibliography, including reroute sources; it is not per-row attribution.
CSV/TSV carry these structured fields as JSON cells, with requested value columns
alongside them. Their headers now include outcome metadata; consumers should select
columns by name. Partial enrichment still counts as resolved; inspect `missing` to
require every requested field. Human diagnostics continue on stderr.

Fan-out is bounded before child allocation. `weave --max-expansion N` (default
10000) shares one leaf budget across table groups, chunks and traversal phases.
Each original input reserves one slot; if input count exceeds the limit, all roots
remain represented and fan-out adds no extra leaves. Retained children carry a
warning, and `truncations` records the affected root/source row, capability and
requested/kept/omitted successor counts. These counts describe that fork rather
than hypothetical downstream descendants. Truncation keeps the normal exit policy;
inspect `truncations` when complete expansion is required.

**Error tolerance.** A node failing (e.g. one database returns a 500) is *branch-local*:
the weave records it, **keeps the data its other branches already produced**, and tries
to **reroute** around the failed node to the still-missing targets if the graph offers
an alternate path. So a six-database dossier where one source is down still returns the
other five. Each failure is reported on stderr with a category and a plain-English reason
(`upstream unavailable`, `rate limited`, `timeout`, …). An error that left an entity
with *some* of its targets (or was rerouted) is reported but does **not** fail the run;
only an entity left with **no** targets and no alternate route makes the exit non-zero.

The same thing from Python:

## 1. Register weavers, plan, run (the common path)

You register the weavers you want available, say what you *have* and what you *want*,
and run. Braidworks finds the route across all registered weavers. This example
crosses two keyless databases (UniProt → PDBe):

```python
import asyncio
from braidworks.core import BraidRegistry, Braider, LocalExecutor, Strand, StrandSet
from uniprot_weaver import build_uniprot_weaver
from pdbe_weaver import build_pdbe_weaver

async def main():
    registry = BraidRegistry()
    registry.register(build_uniprot_weaver())
    registry.register(build_pdbe_weaver())

    braid = Braider(registry).plan(
        available_types=frozenset({"protein.query"}),
        target_types=frozenset({"protein.name", "structure.pdb.ids"}),
    )

    inputs = [StrandSet.from_strands("p53", [Strand("protein.query", "P04637")])]
    result = await LocalExecutor(registry).execute(braid, inputs)

    for ss in result.resolved:
        print(ss.get("protein.name").value, ss.get("structure.pdb.ids").value)

asyncio.run(main())
```

Pass a list of many `StrandSet`s to process a whole batch in one call. See
[keys-index.md](keys-index.md) for every input/target type and which weaver produces it.

## 2. Read the results

`ExecutionResult` carries entity outcomes and branch diagnostics:

| Bucket | Meaning |
|---|---|
| `resolved` | At least one requested target was produced; inspect completion metadata for other branches |
| `unresolved` | Braid ran but ended in `NO_MATCH` — a valid biological outcome |
| `review_queue` | Ambiguous or review-flagged; a human decision is needed |
| `errors` | Technical failures, including diagnostics for otherwise successful entities |

Use `result.total()` to count distinct terminal entities and `result.fatal_errors()`
to identify blocking failures. Several failed branches can describe one entity,
and a partial success can appear in both `resolved` and `errors`. Fan-out counts
terminal children rather than input roots. Result-scoped `entity_refs` preserve
these relationships through JSON, without assuming input labels are unique.
Legacy JSON without references remains readable but cannot reliably recover
shared entities from its independently serialized buckets.

## 3. Calling one weaver's capability directly

If you don't need routing, call a capability on a single weaver. (Specify `backend`
when the weaver has more than one.)

```python
weaver = build_pdbe_weaver()
results = await weaver.execute_batch(
    "describe_structure",
    [StrandSet.from_strands("e1", [Strand("pdb.id", "1tup")])],
    requested_outputs=frozenset({"structure.pdb.title", "structure.pdb.method"}),
    backend="api",
)
print(results[0].status, {s.type_id: s.value for s in results[0].strands})
```

## 4. Fan-out: one input → many results

`list_*` capabilities that emit a *set* identifier (e.g. `pdb.id`, `go.term`,
`pathway.reactome.id`) can **fan out**: fork one input into an independent child per
result and continue the braid per child (e.g. drill each structure with
`describe_structure`). The default keeps only the single best one.

```python
from braidworks.core import ExpandPolicy

result = await LocalExecutor(registry).execute(
    braid, inputs,
    expand_policy=ExpandPolicy.all(),       # one child per set member
    # ExpandPolicy.top_k(5)  -> keep the best five
    # expand_by_type={"pdb.id": ExpandPolicy.all()}  -> per-type control
    max_expansion=10_000,                   # safety cap on total children
)
```

Each child carries `parent_id` (the originating input's entity id), so you can
regroup fanned leaves by the question that produced them. See
[fanout-roadmap.md](fanout-roadmap.md).

## 5. Example: NCBI taxonomy (and choosing a backend)

`ncbi_weaver` exposes NCBI taxonomy with two interchangeable backends. Build a
weaver with the factory:

```python
from ncbi_weaver import build_ncbi_weaver

# API only — no local data needed (NCBI Datasets v2, over the network)
weaver = build_ncbi_weaver(enable_api=True)

# Local only — explicit prebuilt SQLite DB
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite")

# Local with automatic setup — builds/reuses the DB in the per-user cache.
# On a terminal it prompts before the ~70 MB download + ~1 min build; otherwise
# it honors auto_setup / BRAIDWORKS_AUTO_DOWNLOAD or raises an actionable error.
weaver = build_ncbi_weaver(auto_setup=True)

# Both — local preferred, API as fallback
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite", enable_api=True)
```

The manifest only ever advertises the backends you actually wired in, so a
missing backend never breaks planning — it just isn't an option.

### One-time local DB setup from the CLI

The recommended way to provision the local database once:

```bash
ncbi-weaver ensure              # prompt, then download + build into the user cache
ncbi-weaver ensure --yes        # non-interactive (CI/servers)
ncbi-weaver ensure --refresh    # rebuild from the latest NCBI taxdump
```

`ensure` is idempotent (a valid DB is reused instantly) and, when the DB is
already present, reports whether a newer NCBI release is available. The DB lands
in the per-user cache by default (override with `--db` or `BRAIDWORKS_DATA_DIR`),
so `build_ncbi_weaver(auto_setup=True)` finds it automatically afterward.

Then resolve organism names to taxids exactly as in §1 — register the taxon weaver,
plan from `organism.name` to `ncbi.taxon.id` / `ncbi.taxon.lineage`, and run. The
optional `backend_policy=BackendPolicy.LOCAL_FIRST` prefers the local DB and falls
back to the API:

```python
braid = Braider(registry).plan(
    available_types=frozenset({"organism.name"}),
    target_types=frozenset({"ncbi.taxon.id", "ncbi.taxon.lineage"}),
    backend_policy=BackendPolicy.LOCAL_FIRST,   # optional; needs BackendPolicy import
)
sets = [StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")])]
result = await LocalExecutor(registry).execute(braid, sets)
```

Because `uniprot_weaver` also produces `ncbi.taxon.id`, a protein query can cross
into the organism hub and on to taxonomy/phenotype weavers in a single braid.

## Strand types produced by `ncbi_weaver`

| type_id | group | notes |
|---|---|---|
| `ncbi.taxon.id` | core | matched NCBI tax id |
| `organism.scientific_name` | core | matched scientific name |
| `ncbi.taxon.rank` | core | rank (species, genus, …) |
| `ncbi.taxon.parent_id` | core | immediate parent tax id |
| `ncbi.taxon.match_type` | core | how it matched (exact/synonym/fuzzy/…) |
| `ncbi.taxon.review_required` | core | whether a human should confirm |
| `ncbi.taxon.lineage` | lineage | full ranked lineage (list of `{taxid, rank, name}`) |

Requesting any `core` output computes the whole core group; requesting
`ncbi.taxon.lineage` additionally computes lineage. The cache stores results by
the groups actually computed, so a later `core`-only request is satisfied by a
cached `core`+`lineage` entry.

## Assembling weavers via the factory (optional)

For app-level wiring you can register providers and build by id rather than
calling each `build_*` function directly:

```python
from braidworks.core import WeaverFactory
from ncbi_weaver import NCBIWeaverProvider

factory = WeaverFactory()
factory.register(NCBIWeaverProvider())
weaver = factory.build("ncbi", {"db_path": "data/ncbi_taxonomy.sqlite"})
```

See [architecture.md](architecture.md) for the two-layer factory rationale and
[database.md](database.md) for building the local DB.


## Save a run archive

Add `--archive run.json` to `braidworks weave` or `braidworks run` to save a
self-contained JSON record alongside the usual stdout format. For example:

```bash
braidworks weave --have protein.uniprot.accession=P04637 --want structure.pdb.ids \
  --only pdbe --format csv --archive run.json > structures.csv
```

Use a new filename: an existing archive is never overwritten. The file is written
atomically with owner-only permissions. It retains initial input rows, CLI settings,
effective parameter defaults and overrides, planned routes, terminal outcomes and
executed completion/provenance, source manifests, declared backend fingerprints,
runtime versions, UTC start/end times and citations. Traversal archives store traversal
instructions as their plan; actual steps remain in the execution's completion records.
Unresolved/review/error outcomes are retained when an execution finishes, including
when strict mode returns a nonzero status. A planning failure, interruption or run-level
exception before a terminal result does not produce an archive. Failure to write the
archive returns a nonzero status.

The schema identifier is `braidworks.run-archive.v1`. Read it with any JSON reader;
`records` matches the JSON stdout records, and routed `execution` can be loaded through
`ExecutionResult.from_json`. Direct runs retain each original `WeaveResult` under
`execution.direct_results`. Source manifests include discovered sources; only execution
completion and result references identify those actually used.

Archives retain observations, not copies of provider databases. An API fingerprint may
identify its interface rather than a frozen data release. Saved timestamps are the run
interval, not a timestamp for every HTTP request. Rerunning the same inputs against a
mutable source can produce different results.

## Cache and restart scope

The default local cache is in memory for the lifetime of an executor. Separate CLI
invocations do not share cache entries. A saved archive is inspectable output, not a
resume checkpoint: there is no supported cross-process automatic resume command.
Core exposes a cache protocol for application implementations, but persistent storage
and restart freshness rules remain future work. An arq durable job queue retries steps;
it does not persist the orchestrator's entire braid state. Distributed caching is disabled
by default; see the arq README for its explicit homogeneous-fleet opt-in.

## Browser batches

Run `uv run --no-sync weaverkit serve` after installing the serve extra. In either
builder, enable **Batch inputs**. Paste one identifier per line and choose its input
type, or upload/paste CSV or TSV whose headers are strand types. Empty cells are
absent inputs; shared builder values apply to every row and row values override them.
Duplicates remain separate inputs with a `source_row` identity. Heterogeneous rows
are planned by their available input types before any source calls begin.

The same parameter, backend, ambiguity, confidence and expansion controls apply to
all rows. Expansion uses one budget across the batch. Runs stream progress and can
be cancelled and retried. JSON/CSV/TSV exports include terminal outcomes and lineage;
recipes retain batch text and format, and code generation includes the entire batch.
See [request pacing](request-pacing.md) to control upstream HTTP requests.
