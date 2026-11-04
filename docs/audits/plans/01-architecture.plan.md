# Audit 01 fix plan

Spec: ../specs/01-architecture.spec.md. Status: implementation completed except explicitly deferred findings. See ../README.md for final validation and delivery status. Never count a source-only report as a passing regression.

## A01-01 — Always-computed groups can cause false cache hits with missing output

Status: fixed in current checkout; full workspace/release validation outstanding.

Real executor/shared mapper regression failed before fix: rank then ID produced no resolved identity. Executor now stores a copy with only triggered or emitted cache groups; original computed_groups and mapper output contract unchanged. Both request orders, lookup/resolved/ambiguous mapping and repeated optional absence tested. Existing rich-group and negative cache tests retained unchanged. Core 279 passed. Changed executor.py and test_runtime.py; core 0.11.4 includes this and traversal fix.

Add grouped-cache regression with real mapper/executor; preserve output-group emission contract; reject cache reuse when emitted coverage does not satisfy the next request. Do not remove conformance checks.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A01-02 — Traversal retains stale seed attributes when the join key is already present

Status: fixed in current checkout; full workspace and release checks outstanding.

Evidence: direct-key regression failed with TP53 on every child; chained traversal regression also failed. Re-rooted before every fan and retained input immutability/root lineage. Baseline core 270 passed; after fix 272 passed. Changed traverse.py, test_traverse.py, core patch version 0.11.4. Existing targeted Ruff diagnostics remain; none were introduced by this seam fix.

Reproduce direct-key and chained traversal contamination; re-root every traversal on its consumed join key; retain root lineage; add child-description regressions.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A01-03 — Ambiguous candidate expansion ignores review and confidence safeguards

Status: fixed; user approved default review pause on 2026-10-04.

Core 0.12.0 HALT queues ambiguity before TOP/TOP_K/ALL; RAISE still aborts.
Explicit ALLOW_CONTINUE selects/forks and retains review flags. Positive confidence
floors pause below-threshold candidates or OK strands even with ALLOW_CONTINUE.
Cached ambiguity is interpreted per call without losing candidates; default/opt-in/
default sequence makes one upstream batch. CLI exposes --review-policy and
--confidence-threshold; strict also rejects resolved review flags. Traversal forwards
both settings; fetch preserves review_queue and review_required through JSON.
Browser POST/SSE/prelude runs, recipes, generated code and JSON downloads carry the
effective settings. Actual Firefox default/opt-in/confidence-floor journeys pass.

This is a deliberate public contract change approved by the maintainer, with a minor
core bump and docs/migrating-to-0.12.md. Existing auto-selection tests now explicitly
request ALLOW_CONTINUE; their candidate/fan-out assertions are retained. Confidence
test expectation strengthened to pause. Weaver conformance/contract assertions were
not weakened. Core 383 and toolkit 207 pass; overall 1,177 tests / 45 expected skips.

## A01-04 — Partial-success errors become fatal after JSON round trip; totals double-count entities

Status: fixed; core 307 passed.

Three real-executor regressions failed before the fix: partial success with duplicate labels, identical failed inputs with multiple branch errors, and recovered reroute diagnostics. ExecutionResult now counts unique terminal entities and preserves identity in additive result-scoped JSON entity_refs. Reference validation, legacy decoding and fan-out duplicate-label tests pass. Standalone user IDs remain unchanged; old JSON lacking references cannot recover lost relationships. README/usage/architecture updated. No conformance tests weakened.

Reproduce partial-success JSON round trip and duplicate caller ids; separate stable entity outcomes from diagnostics without relying on object aliasing; test counts/fatality/CLI parity.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A01-05 — Fan-out cap runs after allocation and silently loses leaves from result accounting

Status: fixed in current checkout; core 363 passed, toolkit 178 passed.

20x20 regression allocated 420 clones before fix, now at most 10 for cap 10. Cross-products generated lazily with one clone per retained final combination. Shared reserved-leaf budget spans executor chunks, reroutes, CLI heterogeneous groups and traversal phases. Roots reserve one slot; an input batch larger than the limit is preserved without further growth (existing 25000-input chunk contract retained). Invalid nonpositive/noninteger limits fail before I/O. ExpansionTruncation public JSON type records root/source row, capability, requested/kept/omitted successors and limit; result/CLI/traversal carry it, and children inherit warnings. CLI --max-expansion added. Tests cover candidate/set forks, chunks, successive traversal, exports and source-row coverage. Counts are local omitted successors, not hypothetical final descendants. Docs explain the bound and root exception. Default ambiguity behavior unchanged pending maintainer decision.

Define run-level expansion budget; bound child generation before cloning; emit serializable truncation diagnostics; test cross-products and multi-chunk runs.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A01-06 — Backend policy is applied after choosing the cheapest route

Status: fixed in current checkout; core 352 passed, toolkit 178 passed.

Four LOCAL_ONLY/API_ONLY parallel/multihop regressions failed before fix. Planner now prunes capabilities without a policy-compatible declared backend before Dijkstra/parallel-edge selection. Registry graph remains unchanged. Exclusions still apply, and tests distinguish no type route (NoPathError) from a route blocked by policy (NoPlanError). Unrestricted preference policies still minimize capability cost and assign backends within the selected capability. Runtime configuration is not part of planning. Architecture docs updated; no contract tests weakened.

Add LOCAL_ONLY parallel/multihop route regression; prune unsupported capabilities before shortest-path selection; verify reroute exclusions.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A01-07 — Batch cardinality violations are silently truncated or can misassociate entities

Status: fixed in current checkout; core 338 passed, toolkit 178 passed.

Six short/long dispatch and first/later runner-chunk regressions failed before fix. Shared validation raises exported BatchContractError before mapping/caching/merging, with no fallback for structural violations. Four direct-run/ordinary-weave CLI regressions verify nonzero exit and no partial stdout. Equal-length reordering cannot be detected without correlation IDs; backends retain the documented ordered-response contract. No conformance tests weakened.

Validate one ordered response per input at dispatch and runner boundaries; test short/long batches and chunk alignment without caching mismatched responses.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A01-08 — Successful reroutes omit alternate source references

Status: fixed in current checkout; core 347 passed, toolkit 178 passed.

Actual alternate-route regression extended with provider provenance; initial result included only w_direct before fix. Reroute now merges sub-result references by weaver ID, sorted deterministically. Failed primary remains credited as planned/attempted source; alternate w_s1/w_s2 references retained. CLI export now consumes this bibliography through A03-05.

Merge references from reroute results with stable deduplication; extend existing alternate-source provenance tests.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A01-09 — Cluster budget undercharges oversized batches and does not measure actual HTTP calls

Status: fixed.

Core HTTP hooks charge each actual request, including redirects/pages; all eleven API families and the keyless scaffold use the seam. Process-wide local buckets survive separate event loops; arq replaces input charges with Redis request tokens, capacity one and worker configuration consistency. Regression tests cover redirects, cancellation, concurrent jobs, repeated synchronous loops, bulk input with multiple HTTP calls and Lua configuration mismatch. Real Redis fleet acceptance remains a deployment rehearsal, not locally certified.

## A01-10 — Distributed cache identity uses the orchestrator's data fingerprint, not the worker's

Each executor dispatch sends expected manifest and backend fingerprint; mismatch raises BackendConfigurationError before fetch or retry. Distributed cache disabled by default so cache hits cannot bypass checks. Opt-in assume_homogeneous_workers requires a deployment guarantee; explicit cache rejected without it. Added mismatch/no-cache/opt-in regressions while preserving the existing cache reuse assertion under opt-in. No fleet-wide identity discovery promised.

Status: fixed with safe defaults and explicit deployment contract.

Reproduce worker/orchestrator fingerprint mismatch; define transport fingerprint envelope/handshake and homogeneous-fleet contract; test cache invalidation before advertising heterogeneous workers.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## Completion record

Record per finding: reproduction result, changed files, tests/commands, remaining risks, status (fixed / rejected with evidence / deferred with reason / awaiting decision). Do not mark this whole audit complete while requirements remain unresolved.
