# Plan: Local taxonomy DB auto-setup

**Status:** Implemented (2026-06-06). `weavers/ncbi_weaver/src/ncbi_weaver/setup.py`
(`ensure_taxonomy_db`, `check_for_update`), factory `auto_setup`, the
`ncbi-weaver ensure` CLI subcommand, the actionable local-backend error, and
API-backend INFO logging are all in place and tested. One deviation from the
sketch below: the default DB uses a stable, source-prefixed filename
(`ncbi_taxonomy.sqlite`) rather than a versioned one, so `refresh=True` atomically
replaces in place instead of accumulating ~1.2 GB builds, and the name leaves room
for other taxonomy sources alongside it. This document records the design and the
decisions behind it.

## Problem & philosophy

The `ncbi_weaver` **local** backend needs a SQLite taxonomy database. Today the
user must build it manually (`ncbi-weaver build-db …`) and pass the path. That
is friction, and friction is against the goal of making things easy.

The goal: a user who wants `local` should be able to get a working database
without hunting through docs — but **transparently** (they always know what's
happening) and **in check** (nothing heavy or surprising happens unrequested).
The **api** backend stays zero-setup: it works over the network and just logs
that it is doing so.

## Cost model (important — it's smaller than it sounds)

- **Download:** NCBI `taxdump.tar.gz` is ~60–70 MB. Fast.
- **Build:** parse `names.dmp`/`nodes.dmp` → SQLite. After the DB compaction
  (dropping the denormalized lineage cache in favor of a parent-pointer walk), the
  result is **~1.2 GB on disk, ~44 s to build** (was 3.7 GB).

So the cost of auto-setup is a small download plus a ~1-minute local build — very
reasonable to automate. The things to stay careful about are *build time*, *disk
use*, and *not doing it at a surprising moment*.

---

## Decisions

Three decisions shaped the design. Each option we considered is explained below,
with the trade-off and what we chose.

### Decision 1 — What happens in a non-interactive context when the DB is missing?

"Non-interactive" = no TTY: a server, a CI job, or library code. (Interactive
terminals are handled separately — see the design: they prompt.)

- **Option A — Require opt-in. ✅ CHOSEN.**
  Without explicit consent (`auto_setup=True`, or the env var
  `BRAIDWORKS_AUTO_DOWNLOAD=1`), the weaver does **not** build. It raises an
  *actionable* error that quotes the exact command/flag to fix it. Heavy work
  (a ~1-minute build, network, ~1 GB of disk) never fires unless someone asked
  for it.
  *Why chosen:* predictability. A server request or CI step should never silently
  stall for a minute building a database. Consent is one flag/env var away, and
  interactive users still get a prompt, so it stays easy without being surprising.

- **Option B — Auto-build by default.**
  Build automatically anywhere the DB is missing, and just log it. Maximally
  "easy," but a multi-minute build can kick off inside a server boot or a CI run
  that never intended to download taxonomy data.
  *Why not:* it trades predictability for convenience in exactly the contexts
  (servers/CI) where predictability matters most.

### Decision 2 — How is the database acquired?

- **Option A — Build locally from the NCBI taxdump. ✅ CHOSEN.**
  Download the ~60 MB authoritative `taxdump.tar.gz` from NCBI and build the
  SQLite locally (~1.2 GB, ~44 s). Nothing to host; the data comes straight from
  the source of truth.
  *Why chosen:* small download, no hosting/trust/versioning burden on us, and the
  build is fast now that the DB is compact. It is the most transparent option —
  the artifact is reproducible from a known NCBI URL.

- **Option B — Download a prebuilt DB we host.**
  Skip the local build by downloading a ~1.2 GB prebuilt SQLite from a release we
  publish. Faster setup, no local CPU.
  *Why not (now):* it makes us responsible for hosting, versioning, and being
  trusted for a multi-hundred-MB/GB artifact, and shifts that bandwidth onto every
  user. Not worth it while local build is ~44 s. (Reasonable future option for
  CPU-constrained environments.)

- **Option C — Support both.**
  Build locally by default; allow opting into a prebuilt download.
  *Why not (now):* more surface to build and maintain before it's earned. Revisit
  if a real need for the prebuilt channel appears.

### Decision 3 — What if a newer NCBI taxonomy release exists than the local DB?

- **Option A — Notify, never auto-replace. ✅ CHOSEN.**
  Keep using the working DB. Optionally compare the local build version against
  NCBI's current release and **log** that a newer one is available; only rebuild
  when the user passes `refresh=True`.
  *Why chosen:* stability and reproducibility. Results don't silently change
  between runs, and the user stays in control of when (and whether) to update —
  while still being *informed* that an update exists.

- **Option B — Don't check at all.**
  Only ever rebuild when explicitly asked; no remote version checks.
  *Why not:* simplest, but the user never learns their taxonomy is stale. The
  "notify" behavior is cheap (a small metadata fetch) and strictly more helpful.

- **Option C — Auto-refresh when stale.**
  Rebuild automatically whenever NCBI has a newer release.
  *Why not:* freshest data, but surprise rebuilds (time/disk) and — worse —
  resolution results can change between two runs with no user action, which breaks
  reproducibility.

---

## Design

### Single source of truth

One function owns "make sure a valid DB exists," in `ncbi_weaver` (domain-specific
— never in `braidworks-core`):

```
ensure_taxonomy_db(path=None, *, auto=False, refresh=False, progress=None) -> Path
    1. resolve path (explicit arg → BRAIDWORKS_DATA_DIR → platformdirs user cache)
    2. if a valid DB exists and not refresh: return it (idempotent, instant)
    3. otherwise it must be acquired — caller must have consented (auto=True);
       interactive entry points obtain that consent by prompting
    4. acquire under a lock:
         download taxdump (temp) → verify md5 → build (temp) → validate → atomic rename
    5. return the path
```

### Where the DB lives (default)

A per-user cache directory via `platformdirs` (e.g.
`~/.cache/braidworks/taxonomy/<build-version>.sqlite`), overridable by an explicit
`db_path=` or the `BRAIDWORKS_DATA_DIR` env var. This is what makes "set up once,
reuse forever" automatic — the user never has to choose a path.

### When acquisition triggers

At **construction** (`build_ncbi_weaver(...)`), never lazily inside `resolve()`.
The ~1-minute build happens where the user wrote the call, visibly — not as a
surprise stall inside batch execution or a server request.

### Three entry points (consent by context)

1. **CLI** (`ncbi-weaver ensure`, plus the existing `build-db`):
   interactive — detects a missing DB, prints the notice (source URL, ~60 MB
   download, ~1 GB result, target path), **prompts `y/N`**, shows progress. This
   is the recommended one-time path; no flags required.
2. **Factory** `build_ncbi_weaver(db_path=None, auto_setup=False, …)`:
   - interactive TTY → prompt (as above);
   - non-interactive → honor `auto_setup` / `BRAIDWORKS_AUTO_DOWNLOAD`, else raise
     the actionable error (Decision 1).
3. **API backend:** orthogonal — no DB; logs at INFO that it is resolving via
   NCBI Datasets v2 over the network.

### Guarantees (transparency + in check), always on

- **Announce before acting:** source URL, sizes, destination, and the build
  version on completion.
- **Integrity:** verify NCBI's published `taxdump.tar.gz.md5` before accepting the
  download.
- **Atomic:** download to a temp file → verify → rename; build to a temp DB →
  validate → rename. Never leave a half-built DB that looks valid.
- **Concurrency:** a lock file so two processes don't build into the same path.
- **Disk precheck:** require headroom (~3–4 GB incl. temp) and fail early with a
  clear message.
- **Idempotent:** a valid DB present → skip instantly. Rebuild only on
  `refresh=True`.
- **Staleness:** per Decision 3 — notify on a newer release, never auto-replace.

---

## Implementation sketch (touch points)

- `ncbi_weaver/setup.py` (new): `ensure_taxonomy_db(...)` + default-path resolution
  (`platformdirs` dependency) + md5 verify + atomic temp→rename + lock + disk check.
- `ncbi_weaver/factory.py`: add `auto_setup` / default-path handling to
  `build_ncbi_weaver`; interactive prompt vs actionable error vs `auto_setup`.
- `ncbi_weaver/backends/local.py`: actionable `BackendConfigurationError` message
  (quote the command) when the DB is absent and setup wasn't requested.
- `ncbi_weaver/backends/datasets_v2.py`: add `logging` (INFO) for network use.
- `taxonomy_tools/cli.py`: add an `ensure` subcommand (prompt + progress);
  `build-db` already exists for the explicit path.
- Tests: mock the downloader/transport (no live network); cover idempotency, the
  opt-in gate, atomic-failure cleanup, and the actionable error.

## Deferred / future

- **Prebuilt-DB download channel** (Decision 2, Option B) for CPU-constrained users.
- **In-RAM topology cache** for the local backend (~25 MB, ~11 µs/lineage) — only
  if profiling shows the ~0.7 ms CTE-walk is a bottleneck.
- **Entry-point `discover()`** to auto-register weaver providers (separate, see
  the two-layer factory in `architecture.md`).
