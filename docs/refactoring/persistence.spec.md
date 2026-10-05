# Round 2 implementation spec: persistence and continuation

Status: specified, not implemented. Tracking:
[#144](https://github.com/rafaelmdc/braidworks/issues/144),
[#143](https://github.com/rafaelmdc/braidworks/issues/143).
Evidence: [P01–P10](../audits/persistence-design.spec.md).
Detailed module design: [persistence refactor](../audits/persistence-refactor-design.md).

## PF01 — Explicit connection ownership

Trace: P01, P04, P08. Core supplies small SQLite resource/transaction helpers;
source packages own schemas and SQL. An owned connection closes on every exit. A
borrowed connection remains open; helpers do not commit/rollback unrelated caller
transactions. Internal NCBI helpers use explicit handles rather than global last-path
state. Preserve public legacy wrappers with documented semantics during migration.
Read-only URI construction handles special characters and never creates missing files.
Writable schema initialization checks the actual connection/database generation;
process-global path memoization is not sufficient. New writable stores record schema
version and reject future incompatible versions clearly.

Acceptance: owned/borrowed cleanup, exception rollback, caller transaction preservation,
missing read-only DB, `?`/`#` paths and replacement-file initialization. No source SQL
moves into core. No ORM or connection-manager hierarchy.

## PF02 — Lock and source-generation ownership

Trace: P02, P03, P08. A live builder retains exclusivity independent of elapsed build
age. Release verifies ownership. Owner death has a tested recovery path. Waiting is
bounded and reports progress; atomic temporary build/publish remains intact. Prefer
standard-library OS locking with a supported-platform contract; do not require Redis.

A source reader/session returns data and identity from the same generation. Existing
backends are bound to a generation; opening a different generation fails clearly and
requires reopening rather than using an old fingerprint. Composite sources include
all output-determining artifacts. New build metadata distinguishes schema/build/content;
legacy identity limits are explicit. Do not hash large files per lookup.

Acceptance: concurrent process builds, live lock older than historical threshold,
crashed owner, competing release/recovery and acquire timeout. Reproduce fingerprint
before replacement/threaded read; ensure no new-generation value is cached under an
old identity. Test GTDB tree and crosswalk identity independently.

## PF03 — Source reads and reviewed history are separate

Trace: P05, P07. NCBI-local review repository owns reviewed decisions and their writable
schema/transactions. Reference readers do not initialize user-history tables. Reuse
existing DecisionRecord and conservative matching rules. Migrate existing colocated
history idempotently to a separate path; do not delete or abandon originals on failure.
Release documentation explains default-path changes and rollback.

Local fetch executes one synchronous batch function through the thread boundary
where necessary, with connection/service lifetime inside that function. Keep ordered
one-record-per-input behavior. Moving work into threads does not promise immediate
termination of already-running synchronous work.

Acceptance: refresh preserves reviewed history; migration repeated/failed runs do not
lose/duplicate decisions; reference-only read-only access works; batch order is stable;
large fixture reads do not block the async heartbeat. Benchmark heavy NCBI batching
before introducing persistent thread-local lifecycle complexity.

## PF04 — Durable lookup cache through the existing port

Trace: P06. Add SQLiteStrandCache implementing existing get/put behavior. Default
execution remains in-memory; persistence is opt-in. Canonical keys and result JSON
have explicit codec/schema versions. Preserve backend/source/weaver/input/effective
parameter identity and computed-group coverage semantics. Validate finite supported
JSON values; do not silently stringify unsupported values into persistent identities.
No pickle. Select valid supersets deterministically.

Use an explicit CachePolicy for positive/negative lifetime and retention. Initial
opt-in defaults: positive TTL 3,600 seconds, negative TTL 300 seconds, maximum stored
payload budget 256 MiB. These are configurable operational defaults, not provider
freshness guarantees. Local source fingerprint changes always invalidate reuse, even
within TTL. AMBIGUOUS entries use positive TTL without bypassing review policy; NO_MATCH uses
negative TTL; ERROR results are never admitted. User-authored review records are not
cache entries. Policy durations and budgets must be finite/nonnegative; zero TTL
disables admission for that category. Enforce expiry on get;
cleanup/eviction uses deterministic oldest-entry order. Payload budget does not promise
an identical physical SQLite file size; document page/WAL/vacuum behavior.

Acceptance: the same adapter contract passes for memory/SQLite where policies apply;
close/reopen reuse, key/default equivalence, group coverage, expiry with fake clock,
negative/ambiguous policy, corruption and retention. Rebuild or migrate incompatible
cache explicitly. Preserve arq cache opt-in/worker identity guards. API contract
fingerprints do not imply a frozen remote dataset.

## PF05 — Serializable execution state before persistence

Trace: P09. ExecutionState contains stable internal identities, active/terminal inputs,
lineage/completion/review/errors, expansion/truncation state and execution cursors.
It has versioned JSON round trips. Runtime handles/callbacks/connections are excluded.
Duplicate user IDs/rows remain distinct. Deterministic result application produces the
next state before checkpoint publication. Existing executor methods remain wrappers.
Traversal and heterogeneous groups share this state/budget; there is one engine.

Acceptance: interrupt by serializing between committed waves/phases, reconstruct in
memory and compare with uninterrupted execution. Include duplicates, branch errors,
review, self-loop traversal, rerouting, fan-out caps and heterogeneous group cursor.
Persist plan/reroute/traversal progress so resumption does not restart completed phases.
Do not treat the existing pre-application progress callback as a checkpoint.

## PF06 — Durable run repository and crash semantics

Trace: P10. RunStore owns create/load/claim/save/finish operations; SQLite implementation
uses one transaction per checkpoint revision. Ownership/revision checks reject concurrent
advancement. Abandoned claims have bounded lease recovery; live claims renew. Persist
complete snapshots initially; normalize large snapshots only after measured need.
Never hold a write transaction during upstream calls or human review.

Validate run definition/options, schema, plan and expected source/worker identities
before continuation. A changed definition/source requires rejecting or explicitly
forking a new run. Committed run-state advancement is exactly once; upstream reads
within an interrupted wave may repeat. Cache and run commits can be independent.
Archives stay independent completed-observation exports. Equal declared API identity
does not prove unchanged remote content: retain observation times and document that
resumption does not freeze live providers.

Acceptance: crash before/during/after save yields old or complete new state; stale
revision/owner cannot commit; concurrent resume only has one owner; expired claims
recover; schema/source/options mismatches are actionable; cache-hit/miss behavior
cannot silently advance run progress. Do not claim cross-host SQLite support.

## PF07 — Shared human cache/resume interfaces

Trace: P10 and #143. Core exposes continuation through the shared application service.
CLI, Python and browser offer equivalent options and terminal data while keeping their
own presentation. Prefer explicit opt-in cache/run-store paths. CLI provides run status
and resume by run ID; browser can list/status/resume local runs; Python can open/load
and continue without a CLI subprocess. Saved review inputs require explicit decisions;
resuming never silently bypasses ambiguity policy.

Acceptance: interface contract matrix matches uninterrupted and resumed experiments;
cancellation leaves a valid last checkpoint; duplicate rows/lineage survive; defaults,
paths and cleanup/retention are documented. Readiness exports and archives remain
compatible. No publication or mandatory new server/framework dependency.
