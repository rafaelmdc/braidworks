# Run queries

Use the CLI for tables and shell pipelines, Python for scripts and notebooks, or the
browser to build a query visually. Each uses installed weavers to connect the inputs
you have to the outputs you request.

Complete the [installation guide](install.md) first. Commands below run from
the checkout with `uv run`; after activating `.venv/bin/activate`, you can
use the bare `braidworks` command. See [sources](choose-sources.md) for local-data setup.

## Query from the command line

Start with a known accession:

```bash
uv run braidworks weave --have protein.query=P04637 \
    --want protein.name,structure.pdb.ids
```

`--have` names an input field and its value. `--want` names the fields to retrieve.
Here UniProt resolves the query and PDBe lists related experimental structures.
These sources must be installed and network-accessible.

For a gene symbol, set the species:

```bash
uv run braidworks weave --have protein.query=TP53 --param organism=9606 \
    --want protein.name,structure.pdb.ids
```

`9606` is the human NCBI taxid. Symbol search returns a representative entry;
an accession is more specific. Check the source's selection rules when interpreting
name-based queries.

### Check your installation

```bash
uv run braidworks doctor
```

`doctor` lists each installed source and whether it is ready, partly ready, or needs a
local database first. It also names sources in the checkout that are not installed.
When a query reports "no route", the error names the input or output that nothing
installed handles, suggests close type names, and says which missing source would
handle it.

### Find fields and preview a route

```bash
uv run braidworks weavers
uv run braidworks keys --produces structure.pdb.ids
uv run braidworks path --from protein.query --to structure.pdb.ids
```

`weavers` lists installed capabilities and their parameters. `keys` shows which
sources produce or consume a field. `path` previews a route without fetching data.
The [key index](../reference/keys-index.md) covers the repository's full catalogue.

### Call one source directly

Use `run` when you already know the capability you need:

```bash
uv run braidworks run pdbe describe_structure --have pdb.id=1tup \
    --want structure.pdb.title,structure.pdb.method
```

`weave` plans across sources; `run` calls one named source capability.

## Process a batch

For a text file containing one accession per line:

```bash
uv run braidworks weave --in-file accessions.txt --in-type protein.query \
    --want protein.name,structure.pdb.ids --format tsv > structures.tsv
```

Create `accessions.txt` with your identifiers before running this command. Blank
lines and `#` comments are skipped. For a supplied gene-symbol list, use
[`examples/genes.txt`](../../examples/genes.txt) with `--param organism=9606`.

For CSV or TSV, use field names as headers. This file can start some rows from
queries and others from exact accessions:

```csv
protein.query,protein.uniprot.accession
P04637,
,P38398
```

Save it as `inputs.csv`, then run:

```bash
uv run braidworks weave --in-file inputs.csv \
    --want structure.pdb.ids --format csv > structures.csv
```

Empty cells are absent inputs. `--have` values apply to every row; row values
override them. Rows are grouped by their present input types and planned before
ordinary routed execution starts. Duplicate rows remain separate inputs.

Read stdin with `--in-file -`. Select `--format human|json|jsonl|tsv|csv` for your
consumer; data go to stdout and progress goes to stderr. See
[results and export fields](check-results.md) for coverage, row identity, and diagnostics.

## Query from Python

Give `get` your IDs, say what they are, and name the fields you want:

```python
import braidworks as bw

result = bw.get(
    ["P04637", "TP53"],
    have="protein.query",
    want=["protein.name", "structure.pdb.ids"],
    organism="9606",
)
print(result.summary())   # 2 inputs · 2 resolved · 0 unresolved · 0 need review · 0 errors
result.to_pandas()        # one row per input; needs: pip install 'braidworks-core[pandas]'
```

Rows are labelled by the value you supplied and keep their order; duplicate inputs stay
separate rows. Each row has a `status` (`resolved`, `unresolved`, `review` or `error`),
one column per requested field, and a `missing` list. `get` also works in a Jupyter
notebook as written.

| Need | Use |
|---|---|
| Rows as dictionaries or a file | `result.rows`, `result.to_csv("out.csv")`, `result.to_csv("out.tsv", sep="\t")` |
| One field per input | `result.column("protein.name")` |
| Rows for one input | `result["P04637"]` |
| Inputs lacking a requested field | `result.missing` |
| Ambiguous matches and their candidates | `result.review` |
| Citations for the sources used | `result.cite()`, `result.references` |
| The route that ran | `print(result.route[0])`, or `print(bw.path("protein.query", "structure.pdb.ids"))` |
| Installed sources and their readiness | `bw.sources()` |

Inputs can be one value, a list of values with `have=`, a list of `{field: value}` rows,
a `{field: [values]}` mapping, a pandas DataFrame with field-named columns, or a
`pathlib.Path` to a CSV/TSV file. Parameters are keywords (`organism="9606"`); use
`params={"resolve_protein": {"organism": "9606"}}` to target one step. Unknown fields
and parameters fail before any source is called, with suggestions. Other options:
`sources="uniprot,pdbe"`, `expand="all"` or `"top:5"`, `for_each="orthologs"`,
`review="allow_continue"`, `min_confidence=0.8`.

To reuse sources and settings across many queries, open a session; it closes the
sources' network connections when the block ends:

```python
with bw.Session(sources="uniprot,pdbe", cache="~/.cache/braidworks/lookups.sqlite") as s:
    names = s.get(["P04637"], have="protein.query", want="protein.name")
    structures = s.get(["P04637"], have="protein.uniprot.accession", want="structure.pdb.ids")
```

Inside your own async code, use `await bw.async_get(...)` or `await s.async_get(...)`.
`fetch` and `async_fetch` remain available for existing scripts; see
[reading Python results](check-results.md#read-python-results) for their result shape.

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
see [weaver configuration](../reference/weaver-configuration.md) and [architecture](../explanation/architecture.md).

## Follow related entities

Listing structure IDs gives a collection. To retrieve the title and method of
each structure, expand the IDs into separate child queries:

```bash
uv run braidworks weave --have protein.query=P04637 \
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
uv run braidworks weave --have gene.ncbi.id=7157 --for-each orthologs \
    --param taxon_filter=9443 --want gene.symbol,gene.organism --format tsv
```

`--traverse CAPABILITY` names a capability explicitly when a relationship is
ambiguous. Traversal implies all-member expansion. `--max-expansion N` sets one
run-wide leaf budget (default 10,000), including all chunks and traversals. Original
inputs remain represented; truncated forks carry warnings and `truncations` metadata.
Check those when your analysis requires complete expansion. Parent and source-row
fields let you regroup children; see [result exports](check-results.md).

## Use the browser

The [browser task guide](use-the-browser.md) covers batches, recipes, exports and saved reviews.

Install `weaverkit` with its `serve` extra as described in
[installation](install.md#start-the-browser), then start:

```bash
uv run weaverkit serve
```

Open the localhost address printed by the server. Choose the input and target fields,
inspect the route, then run it. To process a batch, enable **Batch inputs** and paste
one identifier per line or upload CSV/TSV with field names as headers.

Empty cells, shared values, duplicate rows, parameters, and expansion limits follow
the same batch rules as the CLI. Results show progress, review and errors; export
JSON/CSV/TSV for analysis. Saved recipes and generated commands retain batch settings.
For cache/run paths, use [persistence](cache-and-resume.md); paths refer to the server's disk.

## Configure a run

| Need | Control or guide |
|---|---|
| Restrict discovery to sources you need | `--only uniprot,pdbe` |
| Set a filter or source option | `--param NAME=VALUE`; `--param CAPABILITY:NAME=VALUE` scopes it to a step |
| Choose local/API backends | `--policy local_first|api_first|local_only|api_only` |
| Handle ambiguous resolver matches | `--review-policy halt` by default; explicit `allow_continue` retains review flags |
| Require a minimum confidence score | `--confidence-threshold 0.8`; scores are source heuristics, not calibrated probabilities |
| Save observations and citations | `--archive run.json`; [archive reference](check-results.md#save-a-run-archive) |
| Cache lookups or restart saved work | [Cache and saved runs](cache-and-resume.md) |
| Pace source requests | [HTTP pacing](set-request-rates.md) |

`--strict` also fails on unresolved/review-required outcomes. Partial results still
need coverage checks. Read [results](check-results.md) before using exports in an analysis.
