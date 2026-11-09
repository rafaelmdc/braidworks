# Run the offline demo

Show Braidworks working without a network connection: for a talk, a classroom, or a
check that an installation works before the sources are reachable. The demo runs
canned queries against small samples bundled with each source. Nothing is fetched,
so a slow or unavailable upstream API cannot interrupt it.

The demo needs the toolkit and the sources ([install everything](install.md)). Sources
without bundled samples are left out, and demos they would serve are skipped.

## Run every demo query

```bash
uv run braidworks demo
```

Commands run from the checkout with `uv run` (drop it once Braidworks is installed
with pip). The command first states that the
answers are sample data, then prints each query's table and summary line:

| Demo | Input | What it shows |
|---|---|---|
| `proteins` | TP53 and NOTAGENE (`protein.query`) | Name, PDB structures, Reactome pathways, GO processes, STRING partners and AlphaFold confidence from six sources; NOTAGENE shows how a miss is reported |
| `microbe` | Escherichia coli (`organism.scientific_name`) | BacDive Gram stain and cell shape, and the GTDB species |
| `taxon` | Ursus arctos (`organism.scientific_name`) | A two-step route: Wikidata finds the article, Wikipedia counts its page views |

`braidworks demo --list` prints the same list.

## Run one demo, or export it

```bash
uv run braidworks demo proteins
uv run braidworks demo proteins --format csv > demo.csv
```

`--format` takes the same values as `braidworks get`. CSV, TSV and JSON print a single
table, so they need a demo name.

## Show the browser on the sample data

```bash
uv run braidworks demo --serve
```

This opens the [browser interface](use-the-browser.md) on the same samples. A banner on
every page says it is demo mode, and **Start from an example** offers the demo queries.
Paste other IDs as usual; the samples answer only the IDs they contain, so others come
back `unresolved`. `--port` and `--no-open` work as for `braidworks serve`.

## Use it in Python

```python
import braidworks as bw

result = bw.demo("proteins")
result.to_pandas()
```

`bw.demo` returns the same [`Result`](../reference/python-api.md#bwdemo) as `bw.get`.

## What the demo does not show

The samples are small and fixed; they are not current database records. Counts are
much lower than live answers: a few PDB structures for TP53 instead of hundreds.
Do not cite values from the demo. For real answers, run the same query with
`braidworks get` (the [command reference](../reference/cli/demo.md) lists the options).
