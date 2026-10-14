# Run queries

Use the CLI for tables and shell pipelines, Python for scripts and notebooks, or the
browser to build a query visually. Each uses installed weavers to connect the inputs
you have to the outputs you request.

Complete the [installation guide](installation.md) first. Commands below run from
the checkout with `uv run --no-sync`; after activating `.venv/bin/activate`, you can
use the bare `braidworks` command. See [sources](sources.md) for local-data setup.

## Query from the command line

Start with a known accession:

```bash
uv run --no-sync braidworks weave --have protein.query=P04637 \
    --want protein.name,structure.pdb.ids
```

`--have` names an input field and its value. `--want` names the fields to retrieve.
Here UniProt resolves the query and PDBe lists related experimental structures.
These sources must be installed and network-accessible.

For a gene symbol, set the species:

```bash
uv run --no-sync braidworks weave --have protein.query=TP53 --param organism=9606 \
    --want protein.name,structure.pdb.ids
```

`9606` is the human NCBI taxid. Symbol search returns a representative entry;
an accession is more specific. Check the source's selection rules when interpreting
name-based queries.

### Find fields and preview a route

```bash
uv run --no-sync braidworks weavers
uv run --no-sync braidworks keys --produces structure.pdb.ids
uv run --no-sync braidworks path --from protein.query --to structure.pdb.ids
```

`weavers` lists installed capabilities and their parameters. `keys` shows which
sources produce or consume a field. `path` previews a route without fetching data.
The [key index](keys-index.md) covers the repository's full catalogue.

### Call one source directly

Use `run` when you already know the capability you need:

```bash
uv run --no-sync braidworks run pdbe describe_structure --have pdb.id=1tup \
    --want structure.pdb.title,structure.pdb.method
```

`weave` plans across sources; `run` calls one named source capability.

## Process a batch

For a text file containing one accession per line:

```bash
uv run --no-sync braidworks weave --in-file accessions.txt --in-type protein.query \
    --want protein.name,structure.pdb.ids --format tsv > structures.tsv
```

Create `accessions.txt` with your identifiers before running this command. Blank
lines and `#` comments are skipped. For a supplied gene-symbol list, use
[`examples/genes.txt`](../examples/genes.txt) with `--param organism=9606`.

For CSV or TSV, use field names as headers. This file can start some rows from
queries and others from exact accessions:

```csv
protein.query,protein.uniprot.accession
P04637,
,P38398
```

Save it as `inputs.csv`, then run:

```bash
uv run --no-sync braidworks weave --in-file inputs.csv \
    --want structure.pdb.ids --format csv > structures.csv
```

Empty cells are absent inputs. `--have` values apply to every row; row values
override them. Rows are grouped by their present input types and planned before
ordinary routed execution starts. Duplicate rows remain separate inputs.

Read stdin with `--in-file -`. Select `--format human|json|jsonl|tsv|csv` for your
consumer; data go to stdout and progress goes to stderr. See
[results and export fields](results.md) for coverage, row identity, and diagnostics.

## Query from Python

For an ordinary batch lookup, use `fetch` with explicit input and output types:

```python
from braidworks import fetch

result = fetch(
    "structure.pdb.ids",
    ids=["P04637", "P38398"],
    have="protein.uniprot.accession",
    only=frozenset({"pdbe"}),
)
print(result.column("structure.pdb.ids"))
print("No requested value:", result.unresolved)
print("Pending reviews:", len(result.review_queue))
print("Diagnostics:", len(result.errors))
```

`fetch` discovers installed weavers, plans, and executes. `only` restricts discovery;
`registry` lets an application reuse configured weavers. `want` can also be a list
of fields. Set `have` explicitly: its default is `ncbi.taxon.id`.

For gene symbols, use `have="protein.query"` and `params={"organism": "9606"}`.
Parameters may be bare names or scoped by capability, such as
`{"resolve_protein": {"organism": "9606"}}`; use one form per call.
Unknown parameters and unused scopes fail before source calls.

In a notebook or application with an active event loop, use `async_fetch`:

```python
from braidworks import async_fetch

result = await async_fetch(
    "structure.pdb.ids", ids=["P04637"],
    have="protein.uniprot.accession", only=frozenset({"pdbe"}),
)
```

`fetch` collapses repeated IDs. Use CLI table input or the explicit API below when
duplicate rows need separate identities. See [reading Python results](results.md#read-python-results)
for partial success, review, and serialization.

### Control the registry and executor

Use the lower-level API for configured sources, expansion policies, or custom
execution. This complete script registers two weavers and closes their HTTP clients:

```python
import asyncio
from contextlib import AsyncExitStack

from braidworks.core import BraidRegistry, Braider, LocalExecutor, Strand, StrandSet
from pdbe_weaver import build_pdbe_weaver
from uniprot_weaver import build_uniprot_weaver


async def main():
    async with AsyncExitStack() as resources:
        registry = BraidRegistry()
        for builder in (build_uniprot_weaver, build_pdbe_weaver):
            registry.register(await resources.enter_async_context(builder()))
        braid = Braider(registry).plan(
            available_types=frozenset({"protein.query"}),
            target_types=frozenset({"protein.name", "structure.pdb.ids"}),
        )
        inputs = [StrandSet.from_strands("p53", [Strand("protein.query", "P04637")])]
        result = await LocalExecutor(registry).execute(braid, inputs)
        for entity in result.resolved:
            print({key: entity.get(key).value for key in braid.to_types if entity.has(key)})
        print("Unresolved:", len(result.unresolved), "Reviews:", len(result.review_queue))
        print("Diagnostics:", len(result.errors))


asyncio.run(main())
```

A `Strand` is a typed value; a `StrandSet` holds the values for one input. Passing
many sets processes a batch. For builder options, backend policies, and ownership,
see [weaver configuration](weaver-configuration.md) and [architecture](architecture.md).

## Follow related entities

Listing structure IDs gives a collection. To retrieve the title and method of
each structure, expand the IDs into separate child queries:

```bash
uv run --no-sync braidworks weave --have protein.query=P04637 \
    --want structure.pdb.title,structure.pdb.method --expand all --format tsv
```

`--expand all` follows every returned set member within the expansion budget;
`--expand top:5` follows up to five in the source's ordered set. CLI default `none`
uses the representative behavior without additional leaves. In the explicit Python
API, pass `expand_policy=ExpandPolicy.all()` or `ExpandPolicy.top_k(5)` to `execute`.
This expands related IDs; ambiguous matches still pause under the review policy.

For relationships that return the same type they consume, use an explicit traversal.
With `ncbi_weaver` installed, this follows TP53's primate orthologs:

```bash
uv run --no-sync braidworks weave --have gene.ncbi.id=7157 --for-each orthologs \
    --param taxon_filter=9443 --want gene.symbol,gene.organism --format tsv
```

`--traverse CAPABILITY` names a capability explicitly when a relationship is
ambiguous. Traversal implies all-member expansion. `--max-expansion N` sets one
run-wide leaf budget (default 10,000), including all chunks and traversals. Original
inputs remain represented; truncated forks carry warnings and `truncations` metadata.
Check those when your analysis requires complete expansion. Parent and source-row
fields let you regroup children; see [result exports](results.md).

## Use the browser

The [browser task guide](browser.md) covers batches, recipes, exports and saved reviews.

Install `weaverkit` with its `serve` extra as described in
[installation](installation.md#add-the-browser), then start:

```bash
uv run --no-sync weaverkit serve
```

Open the localhost address printed by the server. Choose the input and target fields,
inspect the route, then run it. To process a batch, enable **Batch inputs** and paste
one identifier per line or upload CSV/TSV with field names as headers.

Empty cells, shared values, duplicate rows, parameters, and expansion limits follow
the same batch rules as the CLI. Results show progress, review and errors; export
JSON/CSV/TSV for analysis. Saved recipes and generated commands retain batch settings.
For cache/run paths, use [persistence](persistence.md); paths refer to the server's disk.

## Configure a run

| Need | Control or guide |
|---|---|
| Restrict discovery to sources you need | `--only uniprot,pdbe` |
| Set a filter or source option | `--param NAME=VALUE`; `--param CAPABILITY:NAME=VALUE` scopes it to a step |
| Choose local/API backends | `--policy local_first|api_first|local_only|api_only` |
| Handle ambiguous resolver matches | `--review-policy halt` by default; explicit `allow_continue` retains review flags |
| Require a minimum confidence score | `--confidence-threshold 0.8`; scores are source heuristics, not calibrated probabilities |
| Save observations and citations | `--archive run.json`; [archive reference](results.md#save-a-run-archive) |
| Cache lookups or restart saved work | [Cache and saved runs](persistence.md) |
| Pace source requests | [HTTP pacing](request-pacing.md) |

`--strict` also fails on unresolved/review-required outcomes. Partial results still
need coverage checks. Read [results](results.md) before using exports in an analysis.
