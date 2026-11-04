# Persistence design audit

Date: 2026-10-05. Related: [#143](https://github.com/rafaelmdc/braidworks/issues/143). Tracking: [#144](https://github.com/rafaelmdc/braidworks/issues/144).
Scope: source database acquisition/readers, taxonomy review persistence, result cache,
archive writer, executor/traversal state, and distributed cache safety. This is a
focused main-agent audit, not a new six-agent review or a database rewrite.
Implementation is intentionally unchanged. Findings marked reproduced have isolated,
small SQLite/filesystem probes; others are source observations or future requirements.
No biological databases were downloaded. No dependencies were installed.

## Recommendation

Keep SQLite and the existing `StrandCache` protocol. First repair resource ownership,
source identity and lock ownership. Then make cache policy explicit and extract one
serializable execution checkpoint boundary. Add a SQLite cache adapter and a separate
run store only after those contracts pass. Keep biological schemas in their weavers.

A source database is a rebuildable reference artifact. A result cache is disposable
memoization. A reviewed decision is user-authored history. A run checkpoint is progress
that must survive interruption. They need separate ownership, retention and migration
rules even if the first writable stores eventually share one SQLite file.

## Findings

| ID | Priority | Evidence | Problem | Smallest useful pattern/change |
|---|---|---|---|---|
| P01 | High | Reproduced primitive; source confirmed | Transaction context is mistaken for connection ownership in NCBI helpers; persistent thread-local readers lack a common shutdown boundary | Resource acquisition/release with explicit owned/borrowed connection scope |
| P02 | High | Reproduced | Cached source fingerprint and newly opened reader can describe different database generations | Immutable source snapshot/handle pairing data access with its identity |
| P03 | High | Reproduced | Age alone reclaims a live builder's lock; release does not verify ownership | Ownership-aware lock/lease with bounded acquisition |
| P04 | Medium | Reproduced | Global initialized-path memoization skips schema initialization after replacement | Connection-scoped schema initialization with version metadata |
| P05 | High before durable writes | Source confirmed | Reference taxonomy and reviewed decisions default to the same database and schema initializer | Separate source reader and reviewed-decision repository; explicit migration |
| P06 | High before durable cache | Source confirmed | Cache identity serialization and entry lifetime have no persistent format/freshness contract | Versioned codec plus small cache admission/freshness policy |
| P07 | Medium | Source confirmed | Several local backends run synchronous SQLite/tree work inside async fetch | Synchronous batch query function executed through an existing thread boundary |
| P08 | Medium | Source confirmed | Validity, metadata and URI connection mechanics differ across sources | Small connection helper and source-specific validators; no generic SQL repository |
| P09 | High before resume | Source confirmed | Executor progress events precede result application; live state uses object identity/private budget state | Explicit execution state/memento and post-commit checkpoint seam |
| P10 | High before resume | Source confirmed | Archives have terminal observations; cache entries cannot establish run progress or worker identity | Narrow run-store repository plus transaction boundary; preserve arq safeguards |

### P01 — Connection ownership and lifecycle

Evidence: `taxonomy_resolver/db.py:connect` accepts either a path or an existing
connection. Helpers such as `initialize_database` use `with connect(...)`, which
commits/rolls back but does not close a newly opened connection. The service has a
useful explicit `close()`, while its backend keeps one service per worker thread.
Disbiome/GMrepo/MONDO/Wikipedia also retain thread-local readers without an explicit
shared lifetime mechanism. This does not prove exhaustion in the ordinary CLI;
long-running browser/worker lifetimes and exceptional exits are the concern.

Define ownership explicitly: a helper-created connection closes on exit; a caller's
borrowed connection remains open and its transaction is not silently committed by
an unrelated helper. Prefer batch-scoped connections initially where cheap. Keep
reuse only where profiling justifies it, with owner-thread teardown. Closing arbitrary
thread-local connections from the main thread is not a safe universal solution.

Official [Python connection-context documentation](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager)
distinguishes transaction handling from connection closure. P01's probe confirms it.

### P02 — Fingerprint/data generation mismatch

Evidence: Wikipedia caches `dump_month` in `fingerprint()` on the calling thread,
then `_lookup()` opens a separate thread-local connection through `asyncio.to_thread`.
The probe fingerprints January, atomically replaces the file with February, and reads
February's value while `fingerprint()` still reports January. Disbiome and other
memoized readers merit the same regression matrix; do not assume the precise failure
was reproduced for every backend. GTDB's cached reference-tree paths also need their
identity represented for tree-placement results, rather than only the crosswalk release.

Choose an explicit refresh contract: an existing backend remains pinned to a source
generation, or detects replacement and requires safe reopening. Obtain identity from
the reader's actual generation. Avoid hashing multi-GB files on every request. For
multi-artifact sources use a composite identity, with build/schema metadata. Preserve
caller-owned snapshots until the associated operations finish.

### P03 — Build lock ownership

Evidence: `core/localdb.py:BuildLock` reclaims any lock older than two hours without
checking whether its owner is alive. The probe supplies the current process PID and
an old timestamp; it is reclaimed. `__exit__` unlinks by path without confirming that
it still owns the file. A long live build can therefore lose exclusivity; this is not
a measured production incident. Waiting has no timeout or progress/cancellation API.

Prefer an OS-held lock where the supported-platform contract permits it, or a tested
ownership token/heartbeat lease. Handle process death, PID reuse and competing reclaim
operations deliberately. Keep atomic temporary build/publication already present.
Do not introduce a distributed lock server for local file acquisition.

### P04 — Initialized-path global state

Evidence: `taxonomy_resolver/cache.py:_INITIALIZED_CACHE_DATABASES` keys paths or
connection IDs for the whole process. Replacing an initialized file with a fresh
SQLite file makes the next initializer return early; the probe then finds no
`reviewed_mappings` table. Connection ID reuse and multiple threads are further risks,
not independently reproduced here. `db.py:connect` also updates a global default path,
so implicit callers depend on the last connection opened anywhere in the process.

Use explicit database handles/paths in internal callers. Check schema on writable
connection initialization and migrate transactionally. Do not use global path history
as proof that a database generation is initialized. Retain public legacy wrappers
until a documented compatibility migration can remove implicit defaults.

### P05 — Source data and reviewed decisions have different owners

Evidence: NCBI `TaxonomyResolverService` initializes reference and review tables in the
taxonomy file. `cache.py` defaults its writable review store to that file; a separate
`cache_db_path` already exists. Reference builds use temporary artifacts and atomic
replacement, while reviewed decisions are historical writes. Refreshing a replaced
source file may discard colocated review history. This audit has not simulated the
entire refresh/review workflow, so that loss is a source-derived risk.

Use the existing separate-path option as the migration starting point. A narrow
review repository can own lookup/record operations and transactions; taxonomy SQL
remains source-local. Plan idempotent export/copy of existing review history before
changing defaults. Make source readers read-only after this separation. Do not move
review semantics into core or call user decisions disposable cache entries.

### P06 — Durable cache policy and codec

Evidence: `core/cache.py` already offers `StrandCache.get/put`; the executor supplies
backend, source fingerprint, weaver version, effective parameters and group coverage.
This is a good port for a SQLite adapter. `compute_cache_key` uses JSON `default=str`,
without a format version; `InMemoryStrandCache` has no expiry or size bound. Executor
admission currently retains every non-ERROR result, including NO_MATCH and ambiguity.
An API fingerprint can identify a stable API contract while live records still change.
These are acceptable short-lived defaults, not a durable freshness specification.

Before persistence, define supported canonical input values, codec/schema version,
finite-number handling, corruption behavior, group superset lookup, positive/negative
expiry and retention. Keep defaulted parameters and existing group-coverage regressions.
Do not call an API version a frozen dataset snapshot. Persist structured JSON rather
than pickle. Add policy only where cache admission/expiry vary; no factory hierarchy.

### P07 — Async boundary for local work

Evidence: GTDB `backends/local.py:fetch` directly opens/queries SQLite and may load tree
files. AGORA's local lookup similarly performs synchronous source operations. Other
backends already use `asyncio.to_thread` with a batch function. Large work can block
browser progress and unrelated tasks; the audit did not benchmark event-loop latency.

Extract a synchronous whole-batch function and move its connection lifecycle into
that function before scheduling it in a thread. Preserve order and cardinality.
Cancellation of an awaiting coroutine does not forcibly stop a worker thread: document
this and keep write/build work outside fetch. Do not wrap each SQL row in its own task.

### P08 — Share mechanics without homogenizing schemas

Evidence: local `db_is_valid` implementations variously test nonempty tables, release
metadata or mere nonempty files. Connection URIs interpolate unescaped paths. Metadata
names differ (`meta`, `metadata`, content hash, release, dump month). These differences
are not automatically bugs: source-specific schemas are legitimate.

Share safe read-only URI construction, owned connection scope and a minimal schema
version convention for new writable stores. Keep source validity and SQL in the source
package. Expand validation only to properties each capability actually requires.
Retain `ensure_local_db`'s callback orchestration: it already expresses the useful
Template Method idea without an inheritance framework. No ORM or schema auto-discovery.

### P09 — A real checkpoint boundary

Evidence: executor `_run` emits `on_event` after wave fetches but before applying
results, creating children and terminal outcomes. Its terminal set uses Python object
identity; expansion budget and traversal progress are private runtime state. Saving
that event or a list of cached results would not describe a committed execution state.

Extract a serializable execution-state value and a pure/deterministic result-application
boundary. It needs stable run/input/child identities, active and terminal entities,
completion metadata, review/errors, next wave/traversal position, expansion usage,
truncations, plans, effective options and source identities. Snapshot only after all
state changes for the chosen boundary. First prove uninterrupted vs serialized in-memory
continuation equivalence. This is a targeted memento/state-machine seam, not event sourcing.

### P10 — Run persistence is separate from memoization

Evidence: `archive.py` captures initial state and final observations; it explicitly
rejects the checkpoint claim. Atomic archive creation is valuable but has no incremental
run lifecycle. Arq disables cache unless homogeneous-fleet identity is asserted; a new
persistent cache must not bypass that guard. Current serialization does not promise
crash-safe wave commits, concurrent resumers or checkpoint compatibility.

Use a narrow `RunStore` only after P09, with a transaction committing a complete
checkpoint and a compare-and-swap revision/claim for a resumed run. A cache write is
not proof that an entity reached its next step. Independent cache and run transactions
are acceptable if a crash causes safe repeat lookup; require exactly-once state
advancement, not exactly-once upstream reads. Resume must reject changed plans/options
or source identities unless the user explicitly starts a new run with new semantics.
SQLite WAL is a candidate for writable stores, not a blanket pragma for source artifacts:
[SQLite WAL documentation](https://www.sqlite.org/wal.html) explains its concurrency,
checkpoint and same-host constraints. No claim of distributed SQLite support is made.

## Patterns worth preserving or rejecting

Preserve Strategy/Adapter at weaver backends, the cache Protocol, callback-based
artifact acquisition, immutable identity values and JSON boundaries. Use resource
scopes, a small repository for reviewed decisions/run checkpoints, and a transaction
boundary only where they reduce observed coupling.

Do not add an ORM, generic CRUD repository for every source, dependency-injection
container, abstract database factory family, CQRS, event sourcing or separate database
server. No present evidence justifies those costs. Do not redesign biological schemas
merely to make them uniform. Do not split the entire executor just to meet a file-size rule.

## Reproduction and limits

Run from the checkout, using the isolated environment:

```bash
UV_PROJECT_ENVIRONMENT="$PWD/.audit-local/tools/venv" uv run --no-sync python docs/audits/reproductions/persistence.py
```
 It creates tiny files
in an automatically removed temporary directory. It confirms P01's primitive, P02,
P03 and P04. No live calls or real biological data are needed. Remaining findings are
source observations or requirements for a future feature, not proven runtime defects.
Existing full-suite results are the preceding branch baseline, not tests of an
unimplemented refactor. See the [staged plan](persistence-design.plan.md).
