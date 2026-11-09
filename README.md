# Braidworks

Braidworks retrieves and connects biological data across databases. Give it the
identifiers or names you have and the fields you want; it finds a route through
installed data sources and runs the lookups for your inputs.

For example, a protein query can resolve through UniProt to an accession, then use
that accession to retrieve experimental structures from PDBe or pathways from
Reactome. You can work from the command line, Python, or a local browser interface.
Results retain source provenance, citations, missing fields, and review outcomes.

## How it fits together

A **weaver** is an adapter for one source, such as UniProt or NCBI. It declares which
inputs it accepts and which outputs it can provide. A **braid** is a plan that
connects those lookups. Shared identifiers let the output of one weaver become the
input to another.

You choose the data you need; Braidworks handles the connections. Available routes
depend on your installed weavers and configured backends. Public APIs need network
access; some sources require a separately prepared local database. See the
[source catalogue](docs/reference/sources.md) to choose sources for your work.

## Try one query

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
From a terminal, install Braidworks with every source and the browser interface:

```bash
git clone https://github.com/rafaelmdc/braidworks
cd braidworks
uv sync --all-extras
uv run braidworks doctor
uv run braidworks get P04637 --have protein.query \
    --want protein.name,structure.pdb.ids
```

This asks for the name and experimental structure IDs associated with human p53's
UniProt accession, `P04637`. It uses live APIs, so the returned structure inventory
can change. The install creates a local `.venv`; it does not download biological
databases. `braidworks doctor` checks the installation and tells you what to fix.

For gene symbols, constrain the species, for example `braidworks get TP53
--have protein.query --param organism=9606 …` for human. UniProt search returns one representative, which
is not an inventory of every matching protein or isoform.

## Choose your interface

Start with a researcher walkthrough:

- [Find experimental structures for a protein list](docs/tutorials/protein-structures.md): connect sources, inspect structures and export a batch.
- [Trace a microbial functional annotation](docs/tutorials/microbial-functions.md): follow a taxonomy-based affiliation back to its rule evidence.
- [Inspect disease–microbe associations](docs/tutorials/disease-associations.md): retain provider identity, study context and publication evidence.

| You want to… | Start here |
|---|---|
| Run a query from the shell | [Run a query](docs/how-to/run-queries.md) |
| Export a batch to a spreadsheet | [Process a batch](docs/how-to/process-a-batch.md) |
| Retrieve values in a script or notebook | [Python tutorial](docs/tutorials/first-analysis-in-python.md), then [Work in Python](docs/how-to/work-in-python.md) |
| Build and run a query visually | [Browser tutorial](docs/tutorials/first-query-in-the-browser.md), then [Use the browser](docs/how-to/use-the-browser.md) |
| Find available fields and source requirements | [Find a field](docs/how-to/find-a-field.md), the [source catalogue](docs/reference/sources.md) and [key index](docs/reference/keys-index.md) |
| Check missing data, ambiguity, and failures | [Reading results](docs/how-to/check-results.md) |
| Reuse lookups or continue a saved run | [Cache and saved runs](docs/how-to/cache-and-resume.md) |

A result marked resolved may still have missing fields. Keep coverage and review
information alongside your data; an empty source lookup does not establish
biological absence. The [documentation index](docs/index.md) links to the full guides.

## Contribute

Braidworks is a `uv` workspace with a domain-neutral core, source-specific weavers,
and `weaverkit` for creating and verifying adapters. Start with
[CONTRIBUTING.md](CONTRIBUTING.md) for setup and [AGENTS.md](AGENTS.md) for repository
contracts. The [architecture](docs/explanation/architecture.md) explains the boundaries.

```bash
make sync
make lint
make test
```

New weavers follow the spec → scaffold → implement → verify loop described in
[weaverkit](weaverkit/README.md). Each package versions independently; installation
currently uses the checkout or built wheels. See [installation](docs/how-to/install.md)
for other setups and [release rehearsal](docs/how-to/release.md) for maintainers.

## License and attribution

The software is [MIT licensed](LICENSE). Biological data retain their providers'
licenses and attribution requirements. Run `uv run braidworks references`
to inspect references from your installed sources.
