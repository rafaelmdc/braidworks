# Usage

Install → register weavers → plan → run. Most weavers are keyless public APIs and
need no setup; the taxonomy weaver additionally offers a local DB backend (covered
last).

## Install

```bash
uv sync --all-extras
```

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
Data goes to **stdout**, progress + a resolved/unresolved/review count to **stderr**,
so pipes stay clean. Exit code is non-zero only on a structural error (a `NO_MATCH` is
valid data) — add `--strict` to also fail on any unresolved/review input.

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

Every input lands in exactly one bucket of `ExecutionResult`:

| Bucket | Meaning |
|---|---|
| `resolved` | Target strands produced; the braid ran to completion |
| `unresolved` | Braid ran but ended in `NO_MATCH` — a valid biological outcome |
| `review_queue` | Ambiguous or review-flagged; a human decision is needed |
| `errors` | Structural failure — missing inputs, no route, backend exhausted |

`len(resolved) + len(unresolved) + len(review_queue) + len(errors)` always equals
the number of inputs.

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

`taxon_weaver` exposes NCBI taxonomy with two interchangeable backends. Build a
weaver with the factory:

```python
from taxon_weaver import build_ncbi_weaver

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
taxon-weaver ensure              # prompt, then download + build into the user cache
taxon-weaver ensure --yes        # non-interactive (CI/servers)
taxon-weaver ensure --refresh    # rebuild from the latest NCBI taxdump
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

## Strand types produced by `taxon_weaver`

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
from taxon_weaver import NCBIWeaverProvider

factory = WeaverFactory()
factory.register(NCBIWeaverProvider())
weaver = factory.build("ncbi", {"db_path": "data/ncbi_taxonomy.sqlite"})
```

See [architecture.md](architecture.md) for the two-layer factory rationale and
[database.md](database.md) for building the local DB.
