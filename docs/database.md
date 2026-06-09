# NCBI Taxonomy Database

The `taxon_weaver` **`local` backend** resolves names against a local SQLite copy
of the NCBI taxonomy. The **`api` backend** uses NCBI Datasets v2 remotely and
needs **no database** — if you only use `api`, skip this page entirely.

Braidworks never downloads the database implicitly: it is ~4 GB once built, so
acquisition is an explicit, one-time step.

## Build it (download + build in one step)

A console script (`taxon-weaver`) ships with the `taxon_weaver` package:

```bash
# from the repo root
uv run --package taxon_weaver taxon-weaver build-db \
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
from taxon_weaver import build_ncbi_weaver

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

## Roadmap: assisted setup

Today you build the DB explicitly, as above. Planned next: when a weaver is asked
for the `local` backend and the database is absent, guide the user through (or, in
a CLI context, offer to run) the download+build — while the `api` backend "just
works" remotely and logs that it is using the network. Until that lands, the
explicit `build-db` step above is the supported path.
