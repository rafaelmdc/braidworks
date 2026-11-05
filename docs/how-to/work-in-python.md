# Work in Python

Recipes for the Python API, `import braidworks as bw`. New to it? Start with
[your first analysis in Python](../tutorials/first-analysis-in-python.md). Every
function and option is in the [Python API reference](../reference/python-api.md).

## Look up a list of IDs

Give `get` your IDs, say what they are, and name the fields you want. If you don't
know a field's exact name, search for it by meaning first:

```python
import braidworks as bw

bw.find("pdb structures", limit=1)
# structure.pdb.ids  Experimental PDB structures of this protein.
#                    (pdbe; from protein.uniprot.accession)
```

Then use the names in `get`:

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
| Ambiguous matches and their candidates | `result.review`; see below to resolve them |
| Citations for the sources used | `result.cite()`, `result.references` |
| The route that ran | `print(result.route[0])`, or `print(bw.path("protein.query", "structure.pdb.ids"))` |
| Installed sources and their readiness | `bw.sources()` |
| A field's exact name, from plain words | `bw.find("pdb structures")` |

Inputs can be one value, a list of values with `have=`, a list of `{field: value}` rows,
a `{field: [values]}` mapping, a pandas DataFrame with field-named columns, or a
`pathlib.Path` to a CSV/TSV file. Parameters are keywords (`organism="9606"`); use
`params={"resolve_protein": {"organism": "9606"}}` to target one step. Unknown fields
and parameters fail before any source is called, with suggestions. Other options:
`sources="uniprot,pdbe"`, `expand="all"` or `"top:5"`, `for_each="orthologs"`,
`review="allow_continue"`, `min_confidence=0.8`.

## Query a batch from a file

Pass a `pathlib.Path` to a CSV or TSV whose header names the field of each column.
A file with one value per line works too when you say what the values are with `have`:

```python
from pathlib import Path

result = bw.get(Path("proteins.csv"), want="structure.pdb.ids", organism="9606")
# proteins.csv:
#   protein.query
#   TP53
#   MDM2
```

Rows keep the file's order and `row` holds each line's position, so duplicate inputs
stay separate. A pandas DataFrame with field-named columns works the same way:
`bw.get(frame, want=...)`.

## Reuse sources and a cache across queries

A session discovers the installed sources once and reuses them. Give it a cache file
to keep every lookup on disk: a repeated query, even in a later session, is then
answered without calling the source again. The `with` block closes the sources'
network connections when it ends.

```python
with bw.Session(sources="uniprot,pdbe", cache="~/.cache/braidworks/lookups.sqlite") as s:
    names = s.get(["P04637"], have="protein.uniprot.accession", want="protein.name")
    structures = s.get(["P04637"], have="protein.uniprot.accession", want="structure.pdb.ids")
```

`sources=` limits routing to those sources; leave it out to use every installed one.
A cache stores observations, not a frozen copy of the database: delete the file to
force fresh lookups. Inside your own async code, use `await bw.async_get(...)` or
`await s.async_get(...)`. For saved runs you can resume later, see
[cache and saved runs](cache-and-resume.md).

## Resolve ambiguous matches

By default, a match the source is unsure about pauses instead of guessing: its row has
status `review` and appears in `result.review` with numbered candidates. Record a
decision for each paused row, then resume. Only the decided rows continue; finished
rows are kept and undecided rows stay paused.

```python
result = bw.get(["bacilus subtilis"], have="organism.name", want="ncbi.taxon.id")
result.review[0]
# bacilus subtilis (row 1) at ncbi.resolve_name: ambiguous, choose one
#   [0] 0.81  ncbi.taxon.id='1630683', organism.scientific_name='Actinocyclus subtilis', …
#   [1] 0.80  ncbi.taxon.id='135461', organism.scientific_name='Bacillus subtilis subsp. subtilis', …
result.review[0].choose(1)    # or .reject(); a flagged (not ambiguous) row takes .accept()
result = result.resume()      # a new Result; the original is unchanged
```

Candidate order and scores come from the source; check the names before choosing.
`min_confidence=0.9` pauses any match scored below that threshold.

## Read list fields and their size

A field that holds several values, such as `go.term` or `structure.pdb.ids`, comes
back whole, as a `bw.Listing`: an ordinary Python list that also knows its size.

```python
terms = result.rows[0]["go.term"]
len(terms)        # how many you have
terms.total       # how many the source has; None if it could not tell
terms.complete    # True when you have all of them
```

A source that had to stop early, for example STRING when you pass
`max_partners=25`, marks its list partial:

```python
result = bw.get(["P04637"], have="protein.uniprot.accession",
                want="protein.interaction.partners", max_partners=25)
partners = result.rows[0]["protein.interaction.partners"]
partners.complete, partners.total   # (False, None): at least 25, true number unknown
```

It displays as `25+`; a partial list whose true size is known displays as
`25 of 321`. To follow each member of a list into a further lookup, pass
`expand="all"` (one row per member) or `expand="top:5"`.

## Export to pandas or a file

```python
frame = result.to_pandas()                       # one row per input
long = result.to_pandas(explode="go.term")       # one row per GO term
result.to_csv("results.csv")                     # or sep="\t" for TSV
```

Exports add a `<field>.total` column after each list field, holding its true size
(empty when unknown or when the row has no value). `to_pandas` needs the pandas
extra: `uv sync --all-extras`, or `pip install 'braidworks-core[pandas]'`.

## Cite the sources

```python
print(result.cite())    # plain-text reference list for the sources this result used
result.references       # the same, as objects with license and citation fields
```

## Control the registry and executor

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
