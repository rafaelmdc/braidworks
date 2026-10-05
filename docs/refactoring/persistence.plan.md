# Round 2 plan: persistence foundations, cache and resume

Spec: [persistence.spec.md](persistence.spec.md). Design:
[persistence boundaries](../audits/persistence-refactor-design.md).
Cross-round order: [W01–03, W09–12](implementation.plan.md).
Status: P01–P03 verified locally; P04 verified locally; P05 verified locally; P06–P07 planned. Tracking: #144, #143, #146.

| Task | Requirement | Deliverable | Dependency |
|---|---|---|---|
| P01 | PF01 | Connection scopes and real schema initialization — verified | W00 |
| P02a | PF02 | Owned build locking with recovery/timeout | P01 |
| P02b | PF02 | Source reader identity/session consistency | P01; coordinate P02a |
| P03a | PF03 | Separate reviewed-history repository and migration | P01–02 |
| P03b | PF03 | Batch-local async thread boundary and lifecycle | P01–02; review P03a service lifetime |
| P04a | PF04 | Versioned cache codec/policy contract | P01; AP01–02 |
| P04b | PF04 | SQLite cache adapter and retention | P04a |
| P05 | PF05 | Serializable state and in-memory continuation | AP02; preserve AP04 progress |
| P06 | PF06 | Transactional run store and ownership | P01–02, P05 |
| P07 | PF07 | Shared human cache/run/resume interfaces | AP03–05, P04b–06 |

## P01 — Connection scope and schema ownership

Inventory `taxonomy_resolver/db.py` call sites accepting paths/borrowed connections.
Add minimal helpers in `core/sqlite.py`; implement read-only URI escaping, owned-close
and explicitly owned transaction semantics. Convert internal helpers to explicit
handles; leave documented public wrappers. Remove initialized-path global shortcuts
in favor of inspecting the actual writable connection/version. Separate read and
schema-initialization paths. Do not commit/rollback another caller's transaction.

Tests: tiny owned/borrowed DBs, exceptions, nested ownership rejection, missing readonly
path, special path characters, replacement DB and incompatible schema. Reuse the audit
reproduction as a failing regression where applicable. Run core/NCBI suites.
Commit boundary: one resource contract plus its callers; no review migration yet.
Done: all PF01 acceptance passes and legacy wrappers are characterized.

## P02a — Build lock ownership

Inspect supported platforms before choosing the stdlib OS lock implementation and
fallback. Add bounded wait/progress, safe owner release and process-death recovery.
Preserve temporary build/publish. Do not reclaim a live lock by age alone or add Redis.

Tests use subprocesses and tiny files: live long-lived owner, contending builders,
owner exit/crash, waiting timeout and owner release. Avoid flaky sleep-based assertions
where handshakes can coordinate processes. Retain existing atomic build failure tests.
Commit independently from source metadata changes.

## P02b — Reader identity/session consistency

Introduce an immutable identity value and source-local metadata readers. Bind backend
instances to a generation; derive identity from the session that reads results and
reject replacement mismatch. Start with Wikipedia's reproduced cross-thread mismatch,
then apply to affected local backends. New builds record meaningful schema/build/content
identity. Handle legacy metadata with explicit limits, not fabricated content guarantees.
Include GTDB crosswalk/tree composition; protect existing sessions during replacement.

Tests: fingerprint then replacement then worker read; no miskeyed result; same generation
reuses; changed component invalidates. No per-call hashing of real multi-GB artifacts.
Run affected weaver/core contracts and version/core-floor checks.
Done for PF02 only when both P02a and P02b gates pass.

## P03a — Review repository and migration

Extract NCBI-local reviewed-decision operations into `review_store.py`, using existing
DecisionRecord and matching rules. Reference readers cease writable review initialization.
Implement a deterministic separate-path default and compatibility policy; document it.
Migrate history transactionally and idempotently, keeping the source intact on failure.
Do not expand a generic CRUD interface or put taxonomy rules in core.

Tests: repeated migration, interruption/rollback, deduplication, conservative reuse,
readonly reference access, refresh retaining history and old/new constructor paths.
Migration goes in a reviewable commit with rollback docs, not hidden in a lookup helper.

## P03b — Local batch execution boundary

Extract whole-batch synchronous lookup functions and own connections/services inside
that scope before scheduling with `asyncio.to_thread`. Apply to GTDB/AGORA where reads
currently block and simplify other lifetimes as justified. Benchmark representative
synthetic NCBI batches before retaining complicated thread-local reuse.

Tests: order/cardinality, async heartbeat, cleanup on failure and cancellation limits.
Do not spawn one task/connection per row. Document that already-running synchronous
work may complete after cancellation. PF03 completes after both P03 tasks pass.

## P04a — Persistent cache contract

Specify supported canonical JSON values and codec version in `cache_codec.py`. Preserve
effective params and coverage key rules. Implement the small CachePolicy contract:
positive 1-hour, negative 5-minute, ambiguous positive TTL, no ERROR admission, configurable
256 MiB payload budget. Validate numeric options and zero-TTL disabling. Keep in-memory
default and reviewed history outside the cache.

Shared behavior tests cover canonical equivalence, unsupported/nonfinite values,
coverage selection, admission and fake-clock expiry. Check existing executor admission
without introducing a second source of truth for coverage. Commit contract before SQL.

## P04b — SQLite cache adapter

Implement get/put on the existing port with owned short transactions, versioned metadata,
indexed base-key lookup and deterministic coverage selection. Validate loaded JSON,
report corrupt misses, implement expiration/oldest-entry retention and clear migration
or rebuild behavior. Document that payload budget differs from physical file size.

Tests: close/reopen hits, effective-default equivalence, richer/insufficient groups,
expiry/negative/ambiguous data, corruption, incompatible schema, retention and write
rollback. Check worker cache safeguards still hold. No persistent default activation.
Done: PF04 acceptance passes with core and arq integration.

## P05 — Execution state before run database

Extract ExecutionState and versioned snapshots; replace runtime object identity with
stable internal input/child keys without changing public row identity. Move current
result application into deterministic transitions while preserving review/expansion
algorithms. Capture heterogeneous group cursor, traversal/reroute cursor and budget.
Keep runtime handles out of snapshots. Preserve the legacy executor facade.

Tests compare uninterrupted runs with serialization/reconstruction between every valid
wave/phase boundary, entirely in memory first. Include duplicates, self-loops, review,
branch errors, fallback/reroute, capped fan-out and mixed groups. Check post-application
checkpoint hooks separately from existing progress events.
Commit state values/transitions before storage. Do not add resume I/O until PF05 passes.

## P06 — Durable run store

Implement RunDefinition/RunCheckpoint JSON values, narrow RunStore and SQLiteRunStore.
Save complete snapshots atomically with revision and ownership checks. Add bounded
claim lease renewal/recovery. Keep transactions short; no HTTP/human waits while writing.
Validate schema/definition/options/source/worker identity before continuing.

Crash-injection tests cover transaction boundaries; subprocess/concurrency tests cover
competing resumers and expired/live owners. Reject stale revision, incompatible source,
options or schema. Check cache hits never establish progress. Declare repeated reads
inside interrupted waves and live-provider mutability honestly.
Commit the storage/revision contract before human interface activation.

## P07 — Shared interfaces and operational docs

Expose cache/run options and continuation through the AP02 service. Implement CLI run
status/resume, Python load/continue and browser status/list/resume against that service.
Use explicit local paths and preserve in-memory defaults. Resume review requires an
explicit decision; never change ambiguity behavior to make a demo continue.

Tests: interface contract matrix, cancellation with valid last checkpoint, duplicates,
lineage, settings and changed-definition rejection. Rehearse Firefox and real generated
commands. Document paths, leases, retention, schema migration and limits. Archives stay
independent observation exports. Update versions/floors/artifacts and strict gates.
Done: PF07 and W14 integrated acceptance; publication stays deferred.

## Evidence and commit discipline

Each task starts Planned, becomes In progress while edited, and becomes Verified only
with acceptance evidence and local commit hash. Record resolved engineering choices
alongside tests; do not silently change spec defaults. Run relevant package tests, then
workspace checks at coherent checkpoints. Data/tools stay isolated and uncommitted.
Keep source/API behavior unchanged where possible; changed API paths require live E2E.

## P01 implementation evidence — 2026-10-05

Implemented `braidworks.core.sqlite` connection_scope, readonly_uri and transaction.
Owned handles always close; explicit transaction ownership rejects nesting. NCBI
internal read/write scopes now use explicit paths/handles, close owned connections,
and preserve active borrowed transactions. A fresh borrowed write commits only the
transaction it starts; commit=False requires a borrowed handle. Legacy connect() still
sets the documented no-path default for compatibility, but internal scopes do not.
Read paths do not initialize/create files. Builds now explicitly close their handle.
Schema version 1 is stored in source-local taxonomy_schema; future versions reject.
Actual databases are checked instead of initialized-path memoization, including replacement.
Review-history separation remains P03, not part of this change.

Evidence: core 403 passed; NCBI 121 passed/11 skipped; full workspace Make test passed;
make lint and NCBI strict verification passed. Ten new regression tests cover ownership,
rollback, borrowed transactions, special/missing paths, replacement and future schema.
No API backend changed; no live network tests or data downloads were required.
Core 0.13.1; NCBI 0.2.3 with core floor 0.13.1. Isolated uv environment retained.
The broad unscoped ruff check also reported five existing findings in docs/diagrams and
tools/release_tags.py outside the Make lint targets; those files were not changed.
Local commit: see git log entry `refactor(sqlite): make connection and schema ownership explicit`.

## P02a implementation evidence — 2026-10-05

BuildLock uses POSIX flock or Windows byte-range locking on a stable file. Kernel
ownership ends on process death; age never evicts a live owner. Acquisition accepts a
finite nonnegative timeout and optional wait progress callback. Unsupported OSes fail
clearly. Release closes this owner's handle and never unlinks a contender's inode.
The old lock-file-removal assertion was deliberately replaced with persistent-inode
and successful-reacquisition assertions: unlinking would violate mutual exclusion.
18 targeted tests and 408 core tests passed, including real spawned-process timeout,
old live owner, process termination recovery, repeat release and invalid timeouts.
Linux POSIX behavior tested; Windows implementation requires Windows CI validation.
Atomic build-failure tests retained. No fallback based on stale timestamps or Redis.
Local commit: see `fix(localdb): use process-owned locks with bounded acquisition`.

## P02b / P03b local-source session evidence — 2026-10-05

SourceIdentity is an immutable JSON value; SourceBinding owns read-only batch sessions
with a SQLite read transaction, source-local metadata and local artifact stamps.
Bindings reject replacement/in-place changes and require a new backend. SQLite WAL and
GTDB tree components participate; no per-query hashing of large files. Metadata/results
come from one connection snapshot. New builds record schema/build identifiers alongside
existing release/content metadata. Wikipedia and GTDB reproductions now reject stale
fingerprints, including unchanged release tags and changed trees. Legacy stamps guard
local generations but are not portable content digests. No remote immutability claimed.

Wikipedia, Disbiome, GMrepo and MONDO readers close per batch. GTDB and AGORA schedule
one whole synchronous batch through asyncio.to_thread, retaining ordering/cardinality.
Tests include JSON roundtrip, same-generation reuse, replacement before/during sessions,
component identity and async heartbeat. Workspace suite and lint passed before commit.
NCBI integration depends on P03a and is recorded separately below.
Local commit: see `refactor(sources): bind local readers to artifact generations`.

## P03a / NCBI P02b–P03b evidence — 2026-10-05

Source-local ReviewedDecisionRepository owns history; reference sessions open read-only.
Default history is a separate sibling `.reviews.sqlite`; explicit cache paths and legacy
same-path configuration remain supported. Idempotent migration copies complete legacy
rows/markers in one transaction and never deletes originals; duplicate original rows
are retained. Failed imports roll back both markers and copies. Refresh retains history,
while conservative build-version matching refuses stale reuse. Operational/rollback
instructions are in docs/database.md. A former mock-only service test was deliberately
replaced with real read-only behavior assertions; conformance/contract checks unchanged.

NCBI now owns one service per batch with a borrowed SourceBinding reference session;
service closure preserves borrowed handles and closes its review repository. Metadata
and rows share a pinned generation, replacement rejects even across worker threads.
Fixture benchmark: 100 rows 0.006s direct/0.009s batch-thread; 1000 rows 0.077s/0.052s.
No persistent thread-local lifecycle is justified by that evidence. Already-running
thread work may complete after cancellation. Core/local source suites, strict gates
and workspace lint pass; final full workspace verification is recorded in the log.
Local commits: P02a ed87656; six-source session change 3615baf; NCBI review change see
`refactor(ncbi): separate reviewed history from read-only reference sessions`.

## P04a–P04b implementation evidence — 2026-10-05

Versioned cache_codec rejects unsupported/nonfinite values rather than stringifying
persistent identities. Historical finite JSON input fingerprints remain compatible.
CachePolicy implements the specified configurable 3600s positive/ambiguous and 300s
negative TTLs, no ERROR admission, zero-category disabling and 256 MiB payload budget.
SQLiteStrandCache implements the existing port with short owned connections/transactions,
versioned schema/codec checks, indexed base-key lookup, expiry and deterministic smallest
valid group-superset selection. Loaded identity/coverage/JSON is validated; corruption is
logged and treated as a miss. Retention evicts oldest observations deterministically;
large payloads are not retained. Physical SQLite page/WAL size is not the payload budget.
Memory remains the default; reviewed decisions stay outside lookup cache. API backend
identity does not freeze live providers. Cache commits do not establish run progress.

Core 448 tests pass, including adapter coverage contracts, reopen/fake-clock expiry,
negative/ambiguous review retention, disabled TTL/budget, codec/policy validation,
corruption/future-schema rejection, deterministic retention and transaction rollback.
Existing executor coverage admission remains authoritative. Core 0.15.0 exposes
SQLiteStrandCache and CachePolicy. Human interface configuration is reserved for P07.
Executed P04 after its AP01–02 dependency while keeping unrelated application tasks
planned, per the user's request to implement one plan at a time.
Local commit: see `feat(cache): add opt-in SQLite cache with versioned policy and codec`.

## P05 implementation evidence — 2026-10-05

ExecutionState captures chunk/wave/reroute cursors, active/terminal internal row keys,
results, review/errors, expansion counter and options. QueryExecutionState adds the
heterogeneous-group/traversal/prelude/target cursor and active executor state. Values
roundtrip through versioned JSON with shared entity aliases and expansion budget restored.
Internal node keys distinguish duplicate labels; public entity/source_row/parent labels
remain intact. Legacy execute/run_traversed/execute_query are facades over this engine.
Fetched waves use the existing deterministic application algorithm, now isolated in
_apply_wave; source/cache I/O stays outside it. Checkpoint observers run after application
and phase/cursor advancement. Interrupted unapplied waves cannot be serialized/reused;
load the last complete checkpoint. Runtime handles are excluded. No run-store I/O yet.

Thirteen boundary tests reconstruct at every wave/chunk/reroute/query phase, with fresh
executors/caches, and compare complete outcomes/alias counts with uninterrupted runs.
Coverage includes duplicates, heterogeneous groups, two self-loop traversals, bounded
set/candidate fan-out, errors/reroutes, unresolved/review and cancellation. Completed
waves and completed queries do not call sources again. Existing core/toolkit contracts
and full workspace suite pass. Core 0.16.0 exposes start_query/continue_query and states.
Local commit: see `refactor(execution): serialize applied waves and query phase cursors`.
