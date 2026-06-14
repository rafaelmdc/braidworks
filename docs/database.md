# NCBI Taxonomy Database

The `ncbi_weaver` **`local` backend** resolves names against a local SQLite copy
of the NCBI taxonomy. The **`api` backend** uses NCBI Datasets v2 remotely and
needs **no database** — if you only use `api`, skip this page entirely.

Braidworks never downloads the database implicitly. Acquisition is an explicit,
opt-in, one-time step — a ~60 MB download plus a ~1-minute local build (~1.2 GB on
disk). The easiest path is `ncbi-weaver ensure` (below); `build-db` is the
fully-manual alternative.

## Easiest: `ncbi-weaver ensure`

```bash
ncbi-weaver ensure              # prompt, then download + build into the user cache
ncbi-weaver ensure --yes        # non-interactive (CI/servers)
ncbi-weaver ensure --refresh    # rebuild from the latest NCBI taxdump
```

`ensure` is idempotent (a valid DB is reused instantly), lands the DB in the
per-user cache (override with `--db` or `BRAIDWORKS_DATA_DIR`), and reports when a
newer NCBI release exists. Afterward `build_ncbi_weaver(auto_setup=True)` finds it
automatically. The design and decisions are in
[local-db-setup-plan.md](local-db-setup-plan.md).

## Manual: build it (download + build in one step)

A console script (`ncbi-weaver`) ships with the `ncbi_weaver` package:

```bash
# from the repo root
uv run --package ncbi_weaver ncbi-weaver build-db \
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

The build prints a summary including the **taxonomy build version** — that string
is the `local` backend's cache fingerprint, so rebuilding from a newer taxdump
automatically invalidates stale cache entries.

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

## Assisted setup (implemented)

`build_ncbi_weaver(auto_setup=True)` provisions the `local` DB on demand: on an
interactive terminal it prompts before the download + build; non-interactively it
honors `auto_setup` / `BRAIDWORKS_AUTO_DOWNLOAD` or raises an actionable error
naming the exact command to run. The `api` backend stays zero-setup — it works over
the network and logs (INFO) that it is doing so. Decisions behind this:
[local-db-setup-plan.md](local-db-setup-plan.md).
