# Audit 06 fix plan

Spec: ../specs/06-usability.spec.md. Status: implementation completed except explicitly deferred findings. See ../README.md for final validation and delivery status. Never count a source-only report as a passing regression.

## A06-01 — Browser run modes do not consistently expose or apply species restrictions

Status: fixed.

Shared route capability metadata and native parameter validation feed graph POST, typed SSE and traversal preludes. Both transports reach recording resolver with organism=9606, wrong scopes reject before I/O, optional unset displayed explicitly. Firefox exercised typed and graph traversal controls and effective settings.

Share route parameter discovery/transport for graph, typed and traversal modes; recording fixture proves organism reaches resolver; display effective settings.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A06-02 — Browser results cannot account for review inputs or identify exported leaves

Status: fixed.

Browser rows use exported domain-neutral core execution_records: resolved/unresolved/review/fatal identities, source row, parent, missing targets, candidates and diagnostics survive. Identifier columns included even when wants are leaf attributes. Mixed repeated-label terminal fixture tested. Firefox table checked and actual JSON/CSV/TSV Blob exports parsed; JSON contains raw ExecutionResult and effective parameters.

Use shared terminal outcome model for browser rows; preserve entity/parent/status/review/candidates and target coverage; test table/download mixed fixtures.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A06-03 — Saving a graph-built recipe silently ignores that experiment

Status: fixed.

Version-2 recipes store active mode, input values, wants, traversal, backend policy, parameters, expansion/k and leaf bound. Legacy typed recipes supported without stale parameter leakage. Firefox graph save/reset/load/legacy journeys passed; storage/validation feedback visible.

Save/load active experiment state including params/traversal/expansion; version recipe schema and support legacy records; test fresh graph save and visible feedback.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A06-04 — “Generated code” does not preserve the selected experiment settings

Status: fixed.

POST /api/code generates artifacts from active settings. CLI includes selected policy, species, traversal and bounds; Python discovers registry and runs asyncio main with same settings. Deterministic tests execute both generated artifacts and compare recording backend calls/outcomes; Firefox inspects graph-generated code.

Generate CLI/Python from effective experiment; complete runnable examples or clear placeholders; test settings parity and supported backend policy translation.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A06-05 — Core graph and modal actions lack keyboard/accessibility equivalents

Status: fixed.

Native search buttons provide Have/Want/Pass-through equivalents; removable chips and code tabs use buttons; inputs have labels; modal has dialog semantics, initial focus, Tab trap, Escape and restoration. Firefox native keyboard actions exercised focus wrapping and restoration; native accessibility computed label checked for search. This certifies the bounded journeys, not full WCAG/contrast/mobile conformance.

Add native keyboard controls/associated labels and dialog focus handling; verify keyboard journeys and accessibility tree with actual browser before claiming conformance.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A06-06 — Searching for the desired biological attribute does not find hidden output fields

Status: fixed.

Operation nodes carry output descriptions from existing toolkit registry. Search includes hidden output IDs/descriptions and provides selectable native result buttons. Firefox biological-process description query finds and selects hidden GO output. No biological assumptions introduced into core.

Search existing output descriptions/leaf fields; expose matching outputs; test biological-process/partners/title discovery without moving domain vocabulary into core.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A06-07 — Graph fan-out has no visible bound control before running

Status: fixed.

Graph and typed modes expose top/top_k/all, k and maximum leaves; graph automatic default is stated explicitly. Deterministic five-member fixture tests both POST and SSE produce 1/3/5 identifiable leaves. Firefox graph traversal bound=1 renders truncation and lineage.

Expose expansion choice/bound in graph mode; show effective cardinality policy; test top/top_k/all across graph and typed flows.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A06-08 — Failed graph previews and stream disconnects provide no actionable feedback

Status: fixed.

Preview no-route errors are textual; SSE disconnect shows reason and retry hint. Starting a run clears earlier outcomes/results button; server cancels unfinished executor task when stream closes. Firefox invalid integer parameter and simulated dropped EventSource both show failures, clear prior results, reenable Run and succeed after correction/retry. Simulated disconnect is distinguished from actual healthy SSE execution.

Show no-route and SSE-disconnect diagnostics; label prior results; fixture failed previews/disconnect/retry preserves coherent state.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A06-09 — Browser batch export lacks a browser batch input journey

Status: fixed.

Both browser builders use batch paste/upload and POST streaming. Shared CLI table parsing preserves duplicates/source rows, heterogeneous routes validate before I/O, and one expansion budget spans the batch. Generated code/recipes/exports retain all rows. Toolkit 221 tests pass; real Firefox paste, recipe, heterogeneous CSV upload, cancellation/server task cleanup and retry journeys pass.

## Completion record

Record per finding: reproduction result, changed files, tests/commands, remaining risks, status (fixed / rejected with evidence / deferred with reason / awaiting decision). Do not mark this whole audit complete while requirements remain unresolved.
