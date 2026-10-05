# Install Braidworks

Python 3.12 or newer is required. The instructions below install from this checkout
or locally built wheels. Package-index publication is still a release decision;
these instructions do not assume that the current versions are on PyPI.

## Start with the molecular CLI

Clone the repository, then install just the sources used by the quickstart:

    git clone https://github.com/rafaelmdc/braidworks
    cd braidworks
    uv sync --package uniprot-weaver --package pdbe-weaver --package quickgo-weaver --package string-weaver
    uv run --no-sync braidworks weavers
    uv run --no-sync braidworks weave --have protein.query=P04637 --want protein.name,structure.pdb.ids

uv creates a project-local .venv. This selection installs core and the four weavers;
it does not install every source's optional dependencies or download biological
databases. Use --no-sync when running commands from the workspace so uv preserves
that selected environment. Alternatively activate .venv/bin/activate and run the
bare braidworks command. Re-running sync with a different selection can remove
packages omitted from that selection; include every package you want to keep.

For the browser, add --package weaverkit --extra serve to that same sync command,
then run uv run --no-sync weaverkit serve. The browser accepts pasted identifiers and uploaded CSV/TSV batches, with the same
execution policies and outcomes as the CLI. See [usage](usage.md).

## Install the complete workspace

    uv sync --all-extras
    uv run --no-sync braidworks weavers

This also installs contributor/test extras and every weaver, including local-data
packages. Installing a package does not acquire its database. AGORA's deflate
archive dependency may require a C compiler when a compatible binary wheel is
unavailable. The selected molecular installation avoids that dependency.

See the [source setup catalogue](sources.md) before enabling a local backend.
Database acquisition is separate from package installation and can be large.

## Install built wheels outside the checkout

Build all independently versioned packages without publishing:

    uv build --all-packages --out-dir /tmp/braidworks-artifacts

In another directory, create a virtual environment and install selected wheels
using their actual filenames, for example:

    uv venv .venv --python 3.12
    uv pip install --python .venv/bin/python /tmp/braidworks-artifacts/braidworks_core-0.12.0-py3-none-any.whl /tmp/braidworks-artifacts/uniprot_weaver-0.2.2-py3-none-any.whl /tmp/braidworks-artifacts/pdbe_weaver-0.1.7-py3-none-any.whl
    .venv/bin/braidworks weave --have protein.query=P04637 --want protein.name,structure.pdb.ids

Install core together with your weavers so dependency resolution uses the local
core artifact. Core alone provides the planner and CLI but no biological sources.
weaverkit is optional; its serve extra supplies the browser server. The arq adapter
is a separate, experimental distributed-execution package.

The [release rehearsal](releasing.md) checks every wheel and source distribution
and performs a clean install automatically. Software is MIT; provider/data licenses
remain independent. Current repository documentation is also available through the
[GitHub documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
