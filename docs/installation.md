# Install Braidworks

Use Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Choose the weavers your analysis needs. Packages install into a virtual environment;
biological database acquisition is a separate step.

These instructions use the checkout or locally built wheels. They do not assume
that current package versions have been published to PyPI.

## Install two sources for a first query

```bash
git clone https://github.com/rafaelmdc/braidworks
cd braidworks
uv sync --package uniprot-weaver --package pdbe-weaver
uv run --no-sync braidworks weavers
uv run --no-sync braidworks weave --have protein.query=P04637 \
    --want protein.name,structure.pdb.ids
```

`uv` creates a project-local `.venv` containing core and these two weavers. Use
`uv run --no-sync` from the checkout so subsequent commands preserve that selection.
Alternatively, run `source .venv/bin/activate` and use bare commands.

To add sources, repeat `uv sync` with **all packages you want to keep**. For example,
add QuickGO and STRING for GO terms and functional associations:

```bash
uv sync --package uniprot-weaver --package pdbe-weaver \
    --package quickgo-weaver --package string-weaver
```

A new selection can remove previously installed workspace packages. See the
[source catalogue](sources.md) for package names and local-data requirements.

## Add the browser

Keep your source selection and include the toolkit's server extra:

```bash
uv sync --package uniprot-weaver --package pdbe-weaver --package weaverkit --extra serve
uv run --no-sync weaverkit serve
```

Open the localhost address printed by the server. The browser accepts single inputs,
pasted identifier lists, and CSV/TSV batches. Continue with [usage](usage.md).

## Install the complete workspace

For development or access to all sources:

```bash
uv sync --all-extras
uv run --no-sync braidworks weavers
```

This includes contributor/test extras and every weaver. Installing a local-data
package does not acquire its database. AGORA's archive dependency may require a C
compiler when a compatible wheel is unavailable; a selected installation avoids
unneeded dependencies.

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

Maintainers can use the [release rehearsal](releasing.md) to validate distributions
and a clean install. Continue with [usage](usage.md) and [reading results](results.md).
