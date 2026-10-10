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

## Assisted setup

`build_ncbi_weaver(auto_setup=True)` provisions the `local` DB on demand: on an
interactive terminal it prompts before the download + build; non-interactively it
honors `auto_setup` / `BRAIDWORKS_AUTO_DOWNLOAD` or raises an actionable error
naming the exact command to run. The `api` backend stays zero-setup — it works over
the network and logs (INFO) that it is doing so. Decisions behind this:
[local-db-setup-plan.md](local-db-setup-plan.md).

## Reader generations and build ownership

Local SQLite backends bind to one generation of the artifact. Fingerprints include
source metadata and local file-generation stamps; GTDB also includes its tree files.
If the database/tree changes, reopen the weaver instead of reusing a backend whose
fingerprint describes another generation. Legacy file stamps are local replacement
guards, not portable checksums. New builders record schema/build identity alongside
available release/content metadata. No large-file hash is computed per lookup.
Batch connections close when work completes. Synchronous batch work runs in threads;
cancellation stops awaiting it but does not terminate an already-running thread.

Builds use local OS advisory locks (POSIX/Windows) and atomic publication. The small
`.lock` file intentionally remains after release; the kernel owns the active lock.
Do not delete it while builds may be running. BuildLock accepts a bounded acquisition
timeout and optional wait callback. Process exit releases ownership automatically.

## NCBI reviewed decisions (from ncbi_weaver 0.2.4)

TaxonomyResolverService opens reference data read-only. Its default reviewed-history
path is `<taxonomy filename>.reviews.sqlite` beside the reference database. Pass
`cache_db_path` to choose another writable local location. This is user-authored
history, independent of the executor's lookup cache.

On open, legacy colocated reviewed_mappings are copied transactionally to the separate
store. Repeated migration does not duplicate rows; failed imports roll back and leave
the original untouched. Copies retain the existing conservative reference-build/name/
level matching rules. Reference refresh keeps the separate history file; decisions from
another build remain stored but are not automatically reused.

For rollback to older software, retain the original reference/history artifact. New
reviews live in the separate file and can be used by older constructors via explicit
`cache_db_path`; do not delete either copy. An explicit same-reference cache path remains
a legacy compatibility option, but writes then invalidate a pinned local backend and
require reopening. Shared read-only reference installations should provide a writable
review path explicitly. Neither file belongs in git.

## Other saved data

The taxonomy database is reference data. Executor lookup caches, saved runs, and
observation archives have different purposes and lifetimes. See
[cache and saved runs](persistence.md) for those options.
