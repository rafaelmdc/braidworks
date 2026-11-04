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
[source catalogue](docs/sources.md) to choose sources for your work.

## Try one query

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
From a terminal, install the two sources for this example:

```bash
git clone https://github.com/rafaelmdc/braidworks
cd braidworks
uv sync --package uniprot-weaver --package pdbe-weaver
uv run --no-sync braidworks weave --have protein.query=P04637 \
    --want protein.name,structure.pdb.ids
```

This asks for the name and experimental structure IDs associated with human p53's
UniProt accession, `P04637`. It uses live APIs, so the returned structure inventory
can change. The install creates a local `.venv`; it does not download biological
databases. Keep `--no-sync` when running commands to preserve your selected packages.

For gene symbols, constrain the species, for example `--have protein.query=TP53
--param organism=9606` for human. UniProt search returns one representative, which
is not an inventory of every matching protein or isoform.

## Choose your interface

Start with a researcher walkthrough:

- [Find experimental structures for a protein list](docs/tutorials/protein-structures.md): connect sources, inspect structures and export a batch.
- [Trace a microbial functional annotation](docs/tutorials/microbial-functions.md): follow a taxonomy-based affiliation back to its rule evidence.
- [Inspect disease–microbe associations](docs/tutorials/disease-associations.md): retain provider identity, study context and publication evidence.

| You want to… | Start here |
|---|---|
| Run queries or export a batch to a spreadsheet | [CLI usage](docs/usage.md#query-from-the-command-line) |
| Retrieve values in a script or notebook | [Python usage](docs/usage.md#query-from-python) |
| Build and run a query visually | [Browser usage](docs/usage.md#use-the-browser) |
| Find available fields and source requirements | [Source catalogue](docs/sources.md) and [key index](docs/keys-index.md) |
| Check missing data, ambiguity, and failures | [Reading results](docs/results.md) |
| Reuse lookups or continue a saved run | [Cache and saved runs](docs/persistence.md) |

A result marked resolved may still have missing fields. Keep coverage and review
information alongside your data; an empty source lookup does not establish
biological absence. The [documentation index](docs/index.md) links to the full guides.

## Contribute

Braidworks is a `uv` workspace with a domain-neutral core, source-specific weavers,
and `weaverkit` for creating and verifying adapters. Start with
[CONTRIBUTING.md](CONTRIBUTING.md) for setup and [AGENTS.md](AGENTS.md) for repository
contracts. The [architecture](docs/architecture.md) explains the boundaries.

```bash
make sync
make lint
make test
```

New weavers follow the spec → scaffold → implement → verify loop described in
[weaverkit](weaverkit/README.md). Each package versions independently; installation
currently uses the checkout or built wheels. See [installation](docs/installation.md)
for other setups and [release rehearsal](docs/releasing.md) for maintainers.

## License and attribution

The software is [MIT licensed](LICENSE). Biological data retain their providers'
licenses and attribution requirements. Run `uv run --no-sync braidworks references`
to inspect references from your installed sources.
