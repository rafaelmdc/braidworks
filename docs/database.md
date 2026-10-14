# Prepare the local NCBI taxonomy database

The `ncbi_weaver` **`local` backend** resolves names against a local SQLite copy
of the NCBI taxonomy. The **`api` backend** uses NCBI Datasets v2 remotely and
needs **no database** — if you only use `api`, skip this page entirely.

Database acquisition requires consent. Download size and build duration depend on
the current dump and your machine. Start with `ncbi-weaver ensure` below, or use
`build-db` to choose an explicit taxdump and output path.

## Prepare or refresh the database

Run these commands from the checkout with `ncbi_weaver` installed.

```bash
uv run --no-sync ncbi-weaver ensure              # prompt, then download + build into the user cache
uv run --no-sync ncbi-weaver ensure --yes        # non-interactive (CI/servers)
uv run --no-sync ncbi-weaver ensure --refresh    # rebuild from the latest NCBI taxdump
```

`ensure` is idempotent (a valid DB is reused instantly), lands the DB in the
per-user cache (override with `--db` or `BRAIDWORKS_DATA_DIR`), and reports when a
newer NCBI release exists. Afterward `build_ncbi_weaver(auto_setup=True)` finds it
automatically. The design and decisions are in
[local-db-setup-plan.md](local-db-setup-plan.md).

## Build from a chosen taxdump

A console script (`ncbi-weaver`) ships with the `ncbi_weaver` package:

```bash
# from the repo root
uv run --no-sync ncbi-weaver build-db \
    --download \
    --dump  data/taxdump.tar.gz \
    --db    data/ncbi_taxonomy.sqlite
```

- `--download` fetches the official taxdump from
  `https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz`
  (override with `--download-url`). Omit `--download` if `--dump` already points
  at a taxdump archive you downloaded yourself.
- `--dump` is where the `.tar.gz` is written/read; `--db` is the SQLite output.
- `--report-json PATH` optionally writes a build report (counts, build version).

The build prints a summary including the taxonomy build version. The local backend's
fingerprint combines source/build metadata with artifact-generation identity. Reopen
the weaver after rebuilding so new lookups use the new generation and cache identity.

## Use it

```python
from ncbi_weaver import build_ncbi_weaver

weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite")   # local backend
```

A missing or non-SQLite path raises `BackendConfigurationError` at construction.
A common pattern is to keep the path in an environment variable:

```python
import os
weaver = build_ncbi_weaver(db_path=os.environ["TAXONOMY_DB_PATH"])
```

## Don't commit it

The database and taxdump are git-ignored (`*.sqlite`, `taxdump.tar.gz`,
`/data/`). Keep them out of version control and out of network filesystems
(SQLite over NFS is unsafe — copy to local disk on HPC).

## Assisted setup

`build_ncbi_weaver(auto_setup=True)` provisions the `local` DB on demand: on an
interactive terminal it prompts before the download + build; non-interactively it
honors `auto_setup` / `BRAIDWORKS_AUTO_DOWNLOAD` or raises an actionable error
naming the exact command to run. The `api` backend stays zero-setup — it works over
the network and logs (INFO) that it is doing so. Decisions behind this:
[local-db-setup-plan.md](local-db-setup-plan.md).

## Reader generations and build ownership

Reopen a weaver after replacing its database or related tree files. Its backend is
bound to the source generation it opened. Do not remove lock files while builders
may run. Exact generation, cancellation and locking rules are in
[local-data reference](reference/local-data.md#reader-generations-and-build-ownership).

## NCBI reviewed decisions (from ncbi_weaver 0.2.4)

Shared read-only taxonomy installations need a separate writable reviewed-history
path. Reference refresh preserves that history, but decisions from another reference
build are not reused automatically. Before migration or rollback, retain both artifacts.
See [reviewed-history reference](reference/local-data.md#ncbi-reviewed-history-storage)
for default paths, migration guarantees and legacy compatibility.

## Other saved data

The taxonomy database is reference data. Executor lookup caches, saved runs and
observation archives have different purposes and lifetimes. See
[cache and saved runs](persistence.md).
