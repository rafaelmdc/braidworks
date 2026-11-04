# Concrete persistence refactor design

Related: [audit findings](persistence-design.spec.md), [implementation phases](persistence-design.plan.md),
[#144](https://github.com/rafaelmdc/braidworks/issues/144) and [cache/resume #143](https://github.com/rafaelmdc/braidworks/issues/143).
Status: proposed architecture and implementation work packages. No implementation in
this commit. This document supplies the responsibility/module design missing from the
initial defect-focused plan. Proposed names below are implementation targets, not APIs
that already exist.

## Target responsibilities

The refactor should produce four understandable boundaries:

1. Source packages own biological schemas, SQL queries and result mapping. Core owns
   reusable connection and artifact mechanics, without interpreting biological tables.
2. Lookup orchestration decides cache identity, coverage and freshness. Cache adapters
   own storage and do not plan, resolve ambiguity or advance runs.
3. Execution owns state transitions. Its state can be serialized without depending on
   database connections, worker handles or Python object identity.
4. Run persistence owns checkpoint transactions, revision/ownership and compatibility.
   CLI, Python and browser invoke the same execution/continuation service.

Read-only source artifacts and writable user state remain separate. Use explicit
constructor arguments to compose services; keep existing constructors as compatible
wrappers. No container or global service locator.

## Patterns and their concrete applications

| Pattern | Current coupling | Planned extraction | Why it earns its place |
|---|---|---|---|
| Resource scope | Path/connection borrowing and thread-local connection ownership are mixed | Owned read-session helpers and explicit transaction helper | Guarantees cleanup without committing or closing somebody else's connection |
| Repository | NCBI review persistence is mixed into reference DB helpers | NCBI-local `ReviewedDecisionRepository` | Keeps user history and its transactions independent of source refresh |
| Adapter / port | Core already has `StrandCache` | `SQLiteStrandCache` implements the existing protocol | Adds persistence without changing lookup callers or requiring an ORM |
| Policy object | Executor admission and future TTL/negative caching vary together | One small `CachePolicy` value and an admission function | Makes freshness rules explicit and testable across adapters |
| Memento | Active entities, terminal outcomes and expansion state live in executor locals | JSON-safe `ExecutionState` and `RunCheckpoint` | Enables continuation with the same state, independent of storage |
| Transaction boundary | Future checkpoints need related records committed together | Concrete SQLite run-store transaction for one revision | Prevents half-written checkpoints and concurrent double advancement |
| Existing Strategy / callback orchestration | Backend dispatch and source build callbacks already work | Preserve `WeaveStepRunner`, `BackendBase` and `ensure_local_db` | Reuse proven extension points instead of introducing parallel abstractions |

A repository here means a few operations expressed in the domain's terms. It does not
mean a base class with `create/read/update/delete` for every table. Resource helpers
can be functions; policies can be dataclasses. A pattern name does not require a class.

## R1 — Connection ownership, without a database framework

New internal module: `braidworks.core.sqlite`.

Start with three functions, not a connection manager hierarchy:

- `open_readonly(path)`: safely construct an escaped file URI, open with `mode=ro`,
  yield the connection, and close it in `finally`.
- `connection_scope(handle, *, mode)`: distinguish a supplied connection from a path;
  close only connections created by this scope. Borrowed connections remain owned by
  the caller. Read scopes do not commit writes.
- `transaction(connection)`: commit/rollback an explicitly owned write operation.
  Reject nested transaction ownership initially rather than silently committing the
  caller's work; add savepoints only if a real caller requires nested writes.

Keep connection creation options explicit, including busy timeout and transaction
mode. Enable foreign-key checks for new writable stores that declare foreign keys.
Do not force WAL onto source artifacts or modify every package's SQL conventions.

Refactor `taxonomy_resolver/db.py` helpers through ownership-aware scopes. Require
explicit handles in internal calls; public default-path entry points can remain
legacy wrappers. Separate schema initialization from reads. Replace the process-wide
initialized-path cache with connection initialization that checks a versioned schema.

For Disbiome, GMrepo, MONDO and Wikipedia, first move connection ownership into their
synchronous batch lookup functions. GTDB/AGORA should use the same batch-level lifetime
when moving work off the event loop. For NCBI's heavier service, retain a per-batch
service/session until profiling establishes whether persistent per-thread reuse is
needed; do not replace every query with a new connection.

Acceptance: owned/borrowed behavior, rollback, caller transaction preservation,
replacement-file initialization, read-only failure and filenames containing `?`/`#`.
Measure repeated NCBI batch latency before adopting a more complex reuse strategy.

## R2 — Source identity as a value paired with a session

Add a small immutable `SourceIdentity` value describing source/build/schema identity.
Each weaver extracts it from its own metadata; core treats its fields as opaque.
A source session pairs an owned reader with the identity read from that same reader.
Do not store a SQLite connection inside a JSON/public identity dataclass.

Baseline refresh behavior: an existing backend is bound to a generation. Each new
batch session verifies that it opened that generation. If the artifact was replaced,
fail clearly and require reopening/rebuilding the backend; never return new values
under the previous cached fingerprint. An already-open immutable reader may finish
against the old generation, provided its data and identity still agree.

This requires meaningful build identity in metadata, not merely path/mtime. For
legacy artifacts, use available source metadata and document any inability to detect
same-release content changes. New builds should record content/build and schema IDs.
GTDB tree placement needs a composite identity for crosswalk plus tree artifacts.
Design its multi-artifact acquisition consistency explicitly; a release name alone
must not attest to trees that were never checked.

Preserve the public `fingerprint()` surface. Route it through the identity/session
contract; do not make executor code know source-specific metadata keys. Test the
fingerprint-before-threaded-read replacement sequence that the audit reproduced.

Repair `BuildLock` independently: use an ownership-safe OS lock where feasible, with
an explicit cross-platform fallback if required. Bound acquisition and report waiting.
Keep `ensure_local_db`'s callback workflow and atomic build publication. Do not turn
source acquisition into a polymorphic builder family.

## R3 — NCBI review repository and service composition

New source-local module: `taxonomy_resolver/review_store.py`.

`ReviewedDecisionRepository` exposes only:

- `find_reusable(request, taxonomy_build_version)`;
- `record(decision)`;
- owned connection lifecycle, if it holds a connection.

Its SQLite implementation owns review-table schema/migrations and existing conservative
reuse rules. It returns the existing `DecisionRecord` values. Reference lookup helpers
continue to own taxonomy queries; `TaxonomyResolverService` coordinates resolution
and delegates review lookup/record instead of initializing writable tables in a source
reader. Initially one concrete implementation is sufficient: add a Protocol only if
it improves contract testing or there is a second implementation.

Use the existing separate review path as the migration starting point. Copy old history
idempotently with stable deduplication/decision identity and transaction rollback. Keep
the old file intact until successful migration is verified. Make the default-path change
explicit in release documentation; constructor compatibility must not silently lose
review history. Do not rename reviewed decisions as disposable lookup cache.

## R4 — Cache service responsibilities and SQLite adapter

Preserve `core/cache.py` as the public import surface. Add internal modules:

- `cache_codec.py`: versioned canonical key/result encoding;
- `sqlite_cache.py`: concrete `SQLiteStrandCache` adapter;
- `CachePolicy` and a small admission/freshness function, placed in `cache.py` unless
  their size warrants another module.

Keep `get(key, requested_groups)` and `put(key, result)` unchanged initially. The adapter
can own timestamps/expiry and reject expired entries on `get`. Coverage-superset rules
remain identical to memory storage. Centralize only repeated admission/coverage logic
from `_run_step_over`; do not move review, fallback or rerouting into the cache.

New persistent schema: metadata/version plus entries keyed by versioned base identity
and group coverage, with encoded result, creation/expiry and optional size accounting.
Use indexed base-key lookup, then the same coverage predicate as memory. Determine
selection among multiple valid supersets deterministically. Validate JSON/result schema
on load. Corrupt entries become reported misses according to an explicit policy;
incompatible schema must migrate transactionally or be explicitly rebuilt.

Default stays in-memory. Persistent storage is opt-in. Specify positive/negative
expiry and storage retention before setting defaults; ambiguous lookup candidates
and reviewed decisions have different semantics. Legacy cache key serialization is not
silently relabeled as the new codec. Existing arq homogeneity gates remain in place.

No generic `StorageBackend` shared with run persistence: the two operation contracts
and durability expectations differ. Small low-level SQLite helpers can still be shared.

## R5 — Executor state extraction before adding resume I/O

New modules: `core/execution_state.py` and, if necessary, `core/checkpoint.py`.

Move serializable orchestration state out of `_run_chunk` locals:

- run/input/child identities and lineage;
- active entities and terminal resolved/unresolved/review/error state;
- completion metadata, truncations and remaining expansion budget;
- current plan, wave position, traversal cursor and reroute progress;
- effective parameters/policies and expected source identities.

Keep runtime dependencies (registry, runners, callbacks, connections) out of the state.
Replace `id(ss)` as the terminal key with a stable internal input/child identity. Do not
assume entity IDs are unique: duplicate user inputs must remain distinct. Preserve
`source_row`, public entity IDs and existing outcome identities.

Extract the existing result-application phase into one deterministic transition
function/method. It applies wave results in current sorted order and returns the next
state plus committed progress events. Keep expansion/review algorithms intact initially.
Do not create a hierarchy of one class per state or policy combination.

`LocalExecutor.execute` remains the compatibility facade. It composes fetch/run steps
and applies transitions. Existing `WeaveStepRunner` remains the I/O strategy. Traversal
must use the same state/budget mechanism instead of inventing a second resume engine.
Progress notifications for existing clients remain supported; persistence gets a new
post-application checkpoint hook, separate from pre-application UI progress.

Gate: serialize state between waves and continue entirely in memory; compare with an
uninterrupted run. Include heterogeneous groups, reroutes, errors, review, self-loop
traversal, duplicate rows and limited fan-out. No database resume until this passes.

## R6 — Run repository and transactionally published checkpoints

Only after R5, define a narrow `RunStore` Protocol and `SQLiteRunStore`:

- `create_run(definition, initial_checkpoint)`;
- `load_run(run_id)`;
- `claim_run(run_id, expected_revision, owner)`;
- `save_checkpoint(run_id, expected_revision, checkpoint, owner)`;
- finish/release ownership with explicit status.

Model `RunDefinition` and `RunCheckpoint` as versioned JSON boundary values. A save
transaction atomically checks ownership/revision, writes the complete next state,
and advances the revision. Prefer a complete snapshot first; normalized checkpoint
child tables can be added only when measured state size requires them. Include lease
renewal/recovery for abandoned claims before supporting concurrent long-running resumers.

Use a concrete SQLite transaction rather than a reusable abstract UnitOfWork framework.
Cache writes may commit separately: after a crash, repeating a read or hitting a cache
is acceptable; advancing run state twice is not. Never keep a SQLite write transaction
open while waiting for upstream HTTP or human review.

Resume reconstructs runtime dependencies and validates checkpoint schema, plans,
parameters/policies, source identity and worker guarantees before continuation. Changed
semantics require rejecting resume or explicitly forking a new run. Start at committed
wave boundaries; interrupted waves may repeat reads. Human review continuation needs
an explicit decision record rather than a silent automatic pick.

Expose one continuation service to CLI, Python and browser. CLI/browser flags and run
listing are interface work after the engine is proven. Keep `archive.py` as an export
adapter over run observations, not the checkpoint store or resume implementation.

## Refactor-first commit sequence

| Commit group | Concrete changes | Boundary proven before moving on |
|---|---|---|
| 1 | SQLite ownership helpers; NCBI explicit-handle internals; initialization cleanup | Resource/transaction ownership |
| 2 | Ownership-safe build lock and immutable source identity/session checks | Concurrent builders and source refresh |
| 3 | NCBI review repository/migration; synchronous batch functions scheduled off loop | User-history ownership and async responsiveness |
| 4 | Cache codec/policy; memory contract tests; SQLite cache adapter | Existing cache protocol remains sufficient |
| 5 | ExecutionState; stable internal IDs; result-application transition; in-memory continuation | Execution can resume without a database |
| 6 | RunStore/checkpoint transactions; crash/revision/identity tests | Durable progress is independent of memoization |
| 7 | Shared CLI/API/browser resume interfaces, migrations/docs and package checks | Feature parity and honest operational limits |

Groups 1–3 are the database refactor and defect repair. Group 4 adds durable cache.
Group 5 refactors execution for continuation. Groups 6–7 add durable resume. Each can
be reviewed independently; do not combine them into an unreviewable database rewrite.
Keep local commits/issues and no push until requested. Public changes require coherent
package versions/core floors and preserved contract tests.

The existing defect plan remains the acceptance checklist; this design specifies the
responsibility changes that achieve it. Avoid speculative extension points: if one
of the proposed modules adds no independent contract or removes no meaningful coupling,
keep it as a function in the existing module instead.
