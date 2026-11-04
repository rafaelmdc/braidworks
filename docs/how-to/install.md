# Install Braidworks

Use Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Packages install into a virtual environment; biological database acquisition is a
separate step.

These instructions use the checkout or locally built wheels. They do not assume
that current package versions have been published to PyPI.

## Install everything

```bash
git clone https://github.com/rafaelmdc/braidworks
cd braidworks
uv sync --all-extras
uv run braidworks doctor
uv run braidworks weave --have protein.query=P04637 \
    --want protein.name,structure.pdb.ids
```

`uv` creates a project-local `.venv` containing core, every source, and the browser
interface (about 60 MB; no biological data). Run commands with `uv run` from the
checkout, or run `source .venv/bin/activate` and use bare commands. `uv run` keeps the
environment in step with the checkout, so after a `git pull` it installs any new
source on the next command.

`braidworks doctor` lists the installed sources, which inputs they accept, and which
ones need a local database or credentials before they can answer. Run it whenever a
query reports "no route".

Installing a local-data source does not acquire its database; see the
[source catalogue](choose-sources.md). AGORA's archive dependency may require a C compiler
when a compatible wheel is unavailable.

## Start the browser

```bash
uv run weaverkit serve
```

Open the localhost address printed by the server. The browser accepts single inputs,
pasted identifier lists, and CSV/TSV batches. Continue with [usage](run-queries.md).

## Install only some sources

Most users should install everything. If you need a smaller environment, note that
`uv sync --package …` is an *exact* selection: it **removes** every workspace package
you do not name, including sources a previous tutorial installed. Name all the sources
you want to keep in one command, and run commands with `uv run --no-sync` so `uv` does
not reinstall the rest:

```bash
uv sync --package uniprot-weaver --package pdbe-weaver \
    --package quickgo-weaver --package string-weaver
uv run --no-sync braidworks doctor
```

## Install built wheels outside the checkout

Build all workspace distributions:

```bash
uv build --all-packages --out-dir /tmp/braidworks-artifacts
```

Then, in a separate directory, install core and the selected weaver wheels together.
The glob patterns select the independently versioned wheel filenames produced above:

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python \
    /tmp/braidworks-artifacts/braidworks_core-*.whl \
    /tmp/braidworks-artifacts/uniprot_weaver-*.whl \
    /tmp/braidworks-artifacts/pdbe_weaver-*.whl
.venv/bin/braidworks weave --have protein.query=P04637 \
    --want protein.name,structure.pdb.ids
```

Use a fresh artifact directory containing one version per package. Core provides
planning and the CLI; install weavers to add biological sources. `weaverkit` is optional,
and `braidworks-arq` is the separate experimental distributed adapter.

Maintainers can use the [release rehearsal](release.md) to validate distributions
and a clean install. Continue with [usage](run-queries.md) and [reading results](check-results.md).
