# Audit 03 fix plan

Spec: ../specs/03-cli-api.spec.md. Status: implementation completed except explicitly deferred findings. See ../README.md for final validation and delivery status. Never count a source-only report as a passing regression.

## A03-01 — Header-based stdin is consumed before execution

Status: fixed; core 307 passed.

TSV stdin ordinary/traversal and CSV detection failed before fix. Inputs collected once and reused. CSV/TSV header detection bounded to first header line. Four real subprocess pipe regressions pass with fixture registry and actual CLI/planner/executor; no live source claims.

Collect input once; reuse for plan and execute/traversal; test real subprocess TSV stdin; add explicit CSV delimiter support only with a documented contract.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A03-02 — Broadcast constants make the planner ignore table columns

Sparse-table ordinary/traversal regressions failed before fix; rows now grouped by actual available types. Matching rows still batch (2 query rows -> 1 resolver request). Python traversal also groups mixed direct/name inputs with shared cache and retains root lineage. Ordinary weave plans all groups before I/O; unroutable group aborts planning. Grouped outputs may differ from input order; entity/parent labels are retained.

Status: fixed; core 325 passed; toolkit 178 passed.

Broadcast-constant regression failed before fix and now passes. Available types are derived from actual merged rows; heterogeneous sparse input batches are grouped as recorded above.

Plan from merged row inputs including constants; define grouping for sparse rows; test table+constant route against equivalent Python inputs.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A03-03 — Direct `run` hides structural failures and ambiguity

Status: fixed; core 307 passed.

Direct-run ERROR/review/backend/configuration regressions failed before fix. Error/review/no-match statuses preserved; errors exit nonzero and carry JSON diagnostics; review candidates retained; strict checks review and no-match; declared-backend validation and BraidworksError handling added. NO_MATCH and existing OK paths unchanged.

Preserve direct run OK/NO_MATCH/AMBIGUOUS/ERROR distinctions; surface diagnostics; return nonzero on ERROR; catch known structural exceptions; test exit/status matrix.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A03-04 — Parameter targeting accepts mistakes silently

Wrong CLI scopes and bare/native/mixed facade errors reproduced before fix. Shared parameters.py validates targeting and values before backend calls. Traversal route discovery includes resolution preludes/final route and preserves consumed context. Tests cover bare/scoped organism=9606 reaching resolver, Python traversal wrong scopes before I/O, sync/async facade rejection and valid coercion, and invalid downstream params preventing upstream calls. Low-level executor continues accepting orchestration parameter supersets; user entry points validate effective routes.

Status: fixed for CLI/fetch/traversal; core 325 passed; toolkit 178 passed.

Validate names and capability scopes before backend I/O across CLI/fetch/traversal; include prelude steps; test species typo/wrong scope and effective params parity.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A03-05 — Machine exports cannot fully account for outcomes

Status: fixed in current checkout; core 347 passed, toolkit 178 passed.

Mixed-outcome JSON/CSV/TSV and duplicate-row fan-out regressions failed before fix. Shared ordinary/traversed export builder includes fatal rows once per terminal object and attaches branch diagnostics. Direct run uses the same metadata/numbering shape. source_row survives core clone/restriction/JSON and fan-out; outcome IDs are unique per output. Completion, missing fields, review candidates, warnings, structured errors, confidence/provenance and run-level references are retained; nested delimited cells use JSON. Header change documented in docs/usage.md. Reroute attribution repaired through A01-08. Full archival configuration/retrieval-time capture remains A04-02, not claimed here.

Build shared terminal-outcome records after A01-04 stable accounting; add status and diagnostics to delimited outputs and fatal rows to JSON; preserve unique source-row lineage and references.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A03-06 — `--only` does not isolate imports of excluded weavers

Status: fixed in current checkout; core 338 passed, toolkit 178 passed.

Two excluded broken-plugin regressions failed before fix, including an empty selection. iter_weaver_builders accepts an optional only filter and checks entry-point metadata before ep.load; default discovery remains unchanged. Selected broken plugins still raise their import failure rather than silently disappearing.

Filter entry-point metadata before load; regress excluded broken plugins and included broken-plugin diagnostics.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A03-07 — Traversal and ordinary weave disagree on nonfatal branch errors

Status: fixed; core 307 passed.

Real traversal fixture with one successful description branch and one ERROR failed before fix; now exits zero while reporting diagnostics. Fully blocked leaves still exit nonzero. Both command paths use fatal_errors(); underlying JSON identity fixed via A01-04.

Use shared fatal-error policy across ordinary/traversed weave after A01-04; test partial-success and recovered errors in both interfaces.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A03-08 — FetchResult lacks the promised public serialization boundary

FetchResult JSON archive regression failed with missing methods before fix. Added to_json/from_json composing existing Reference/ExecutionError serializers; nested values, unresolved coverage, references, diagnostics and canonical identifiers survive actual json.dumps/loads. This is the convenience result boundary, not a complete replay/provenance bundle (A04-02 remains open).

Status: fixed; core 325 passed; toolkit 178 passed.

Add FetchResult JSON serializers using existing nested serializers; test actual JSON roundtrip with values/errors/references.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## Completion record

Record per finding: reproduction result, changed files, tests/commands, remaining risks, status (fixed / rejected with evidence / deferred with reason / awaiting decision). Do not mark this whole audit complete while requirements remain unresolved.
