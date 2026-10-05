# Persistence refactoring plan

Related [audit/spec](persistence-design.spec.md) and [cache/resume #143](https://github.com/rafaelmdc/braidworks/issues/143).
Tracking: [#144](https://github.com/rafaelmdc/braidworks/issues/144).
Concrete architecture: [responsibilities, patterns and module refactor](persistence-refactor-design.md).
Status: proposed, no implementation yet. Work stays in this checkout on
`refactor/persistence-foundations`, which includes the six unpushed readiness commits.

| Phase | Scope | Finding IDs | Gate before advancing |
|---|---|---|---|
| 1 | Connection ownership, explicit paths, safe read-only opens | P01, P04, P08 | Owned handles close; borrowed handles remain usable; file replacement initializes correctly; special path characters work |
| 2 | Lock ownership and source snapshot identities | P02, P03 | Live builders cannot lose locks; crash cleanup is safe; refreshed data never uses an old fingerprint; composite artifacts change identity |
| 3 | Separate review history; move blocking reads off the event loop | P05, P07 | Existing review history migrates idempotently; refresh preserves it; source reads work read-only; batch order and event-loop responsiveness hold |
| 4 | Durable cache contract and SQLite adapter | P06 | Memory/SQLite adapters pass the same behavioral contract; reopen reuse, expiry, negative policy, corruption and group coverage hold |
| 5 | Serializable execution state, without database resume yet | P09 | Serialized continuation matches uninterrupted execution, including duplicates, fan-out limits, traversal, review and fallback |
| 6 | Transactional run store and human resume flow | P10 | Crash injection, concurrent resume claims, source mismatch and CLI/browser parity pass |

## Implementation choices to settle in the relevant phase

1. Source refresh: pin an existing backend generation vs require reopening on change.
   Recommended baseline: explicit generation pinning/reopening, with identity derived
   from the same reader snapshot. Resolve multi-file tree datasets in Phase 2.
2. Connection reuse: default batch ownership; retain pooling/thread-local reuse only
   if measured gains justify the lifecycle. Avoid a new required dependency.
3. Review history path: leverage NCBI's existing separate cache path, with a safe
   migration and documented legacy behavior. Do not silently abandon old decisions.
4. Persistent cache: opt-in local SQLite; keep current in-memory default. Define TTL
   and retention as user-visible policy before choosing defaults. Schema changes must
   migrate transactionally or reject clearly; disposable incompatible cache can be rebuilt.
5. Resume granularity: start at fully applied wave boundaries. Traversal phases need
   their own persisted cursor and shared expansion state. Work within an interrupted
   wave may repeat upstream reads; expose this honestly.
6. Resume identity: preserve run/input/child identity, full plans/options/source
   identities and schema version. A change means reject or explicitly fork a new run.
   Preserve distributed worker validation and cache opt-in guarantees.

## Validation and compatibility

Use tiny generated SQLite databases and deterministic mock backends. Include the
four audit reproductions as meaningful regressions while retaining all existing
contract/conformance checks. Use per-package Make targets; all workspace tests and
lint remain required. Run live E2E only if an API backend is changed. Do not download
large reference artifacts as part of this refactor.

Bump core when public APIs/behavior change; bump affected weavers coherently and raise
core floors when required. Regenerate scaffolded vocab only from its spec; NCBI stays
the documented handwritten exception. Update scaffold helpers only after the real
implementation and contract settle. Keep old public entry points as wrappers where
feasible. Do not stage tools, venvs, generated databases or downloaded source archives.

Track implementation phases with issues and local commits. Keep code unpushed until
requested. This plan revokes no earlier safeguards and activates no publication.

## Acceptance scenarios for #143

- Close/reopen a cache and reuse an identical lookup; changed source, version, input,
  parameter or insufficient output-group coverage causes a miss.
- Positive and negative expiry are explicit; expired/corrupt cache cannot masquerade
  as a valid result. Cache size/retention is bounded by policy.
- A failed source refresh retains the prior usable artifact and all reviewed history.
- A live build older than the stale threshold keeps exclusivity; owner death releases
  it safely; acquisition has a clear timeout/progress behavior.
- Interrupt before/after each checkpoint transaction. Reopen with complete state or
  the previous checkpoint, never half a wave or orphaned child lineage.
- Resume preserves duplicate input rows, review queues, errors, branch completion,
  remaining expansion budget, truncations and traversal position.
- Concurrent resumptions cannot both advance one run; incompatible source identities,
  options, plans or checkpoint schemas fail with actionable diagnostics.
- CLI, Python API and browser use the same continuation engine; arq workers retain
  their identity checks. Archives remain usable observations independent of run-store
  checkpoint compatibility.
