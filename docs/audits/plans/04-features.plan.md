# Audit 04 fix plan

Spec: ../specs/04-features.spec.md. Status: implementation completed except explicitly deferred findings. See ../README.md for final validation and delivery status. Never count a source-only report as a passing regression.

## A04-01 — Spreadsheet exports erase outcome status and omit fatal-only entities

Status: fixed through A03-05; core 347 passed, toolkit 178 passed.

Mixed OK/NO_MATCH/review/ERROR/duplicate fixtures verified actual JSON/CSV/TSV exports for both direct run and routed weave. Fatal rows retained, statuses and source-row ordinals match, diagnostics survive. This is the same implementation as A03-05; do not count it as a separate engineering change.

Do not duplicate CLI export work: implement through A03-05; accept only after mixed outcome spreadsheet fixture.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A04-02 — CLI files do not carry the provenance needed to reuse a biological result

Opt-in --archive writes schema braidworks.run-archive.v1 atomically with owner-only permissions and refuses overwrite. Captures initial inputs before mutation, defaults/overrides, planned routes/traversal instructions, complete terminal execution or direct WeaveResults, exported records, manifests/fingerprints, runtime versions, timestamps and references. Tests cover routed/direct/traversal, unresolved strict outcome, no overwrite/temp cleanup and routed execution JSON reconstruction. Run-level abort/interruption produces no archive; observations do not freeze providers.

Status: fixed for completed CLI executions.

Design opt-in archival bundle/sidecar; capture effective params, executed provenance, retrieval time and references; label mutable live datasets; roundtrip fixture archive.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A04-03 — GO aggregation loses annotation evidence and exposes truncated results as ordinary counts

Status: fixed for transparent annotation inventory; no new biological filter promised.

QuickGO adds go.annotation.records (distinct source evidence/qualifier/reference rows)
and go.annotation.coverage (page/source counts, observed rows, completeness and reason).
Existing go.term/count/records joins remain a deduplicated retrieved inventory, not
positive experimental evidence or a complete-source promise. Source_sample refreshed
from an observed live payload. Page caps, missing page metadata and count mismatches
become explicit warnings on LookupRecord/WeaveResult, surviving cache, execution and
exports even when only go.count is requested. Generic warning support remains domain-
neutral and has JSON/mapping tests. Missing rows during incomplete bulk retrieval are
errors, not false biological absence. HTTP 400/404 are clean misses.

Four evidence/completeness regressions failed before repair; all pass now, including
cached exported warning and per-accession cap tests. Live singleton and two-accession
correlation checks pass (4 live tests). Raw qualifiers are preserved without claiming
filter semantics; actual evidence/qualifier filtering remains a future capability knob.
QuickGO 0.1.7, generated vocab and core>=0.12.0 floor coherent.

Reproduce page-cap metadata loss; preserve observed source evidence/qualifiers in compatible detail shape; verify real schema before adding filters; report completeness explicitly.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A04-04 — Symbol resolution selects a representative without a user-visible ambiguity contract

Status: fixed for the existing representative lookup contract.

UniProt README/source catalogue now lead with accessions or explicit organism=9606,
explain reviewed-first/annotation-score/accession tie-break, distinguish one
representative from exhaustive matches/isoforms, and scope determinism to fixed
source data. Clarifies that executor candidate review does not turn this lookup into
an exhaustive resolver. Existing multiple-hit ordering fixtures retained. Added live
species-pinned TP53 known-truth regression: P04637 and human taxid 9606. Latest eight
UniProt live tests pass. No lookup->resolver conversion or candidate API was smuggled
into this repair; such a feature remains a separately scoped option.

Document representative selection and pinned species; add known-truth pinned TP53 test; candidate/list changes require explicit scope rather than silently changing lookup kind.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A04-05 — Several molecular lookup batches still make serial upstream calls

Status: fixed for bounded molecular batches; no global HTTP-rate guarantee.

Observed real bulk endpoints before implementation: PDBe POST best_structures returns
an accession-keyed mapping; QuickGO comma-separated geneProductId returns correlated
annotation rows. PDBe dedups/chunks 100 accessions, restores input order/duplicates,
and never reuses another accession's sole response. QuickGO chunks ten accessions,
shares a scaled page budget, retains per-accession annotation caps/coverage, and
rejects missing/unexpected echoed IDs rather than guessing. Existing bulk describe,
STRING and UniProt ID-mapping paths retained.

AlphaFold/Reactome/UniProt representative searches use core map_bounded with four
workers by default, configurable max_concurrency, ordered results and per-query HTTP
failures. Unexpected exceptions cancel/join siblings before propagation. Controlled
transport tests prove peak two, out-of-order completion, ordering and isolated 503;
core tests prove cancellation and limit handling. Mock request-count tests verify one
bulk request for multiple IDs. All five affected live suites pass: AlphaFold 2, PDBe 5,
QuickGO 4, Reactome 3, UniProt 8. Small two-ID live measurements recorded separately:
all three concurrent lookup backends resolved both without errors. These are smoke
measurements, not throughput benchmarks or requests-per-second certification.
Versions/spec/vocab/floors synchronized; all five strict gates pass.

Inventory request shapes; prefer verified bulk endpoints, otherwise bounded concurrency; mock request-count/order/concurrency; run small live E2E after API edits; patch-bump affected weavers.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A04-06 — Planning documents and generated inventory lag current features

Status: fixed.

NEXT/roadmap and full generated catalogue now describe shipped bridges and current
acceptance gaps. Source catalogue covers every weaver. Demo no longer hardcodes PDB
counts or promises most-recent selection: it describes coverage/resolution/ID ordering.
Demo stops on fatal shell-command failure. Actual live execution succeeds: dossier,
five structure children and 34 primate ortholog children on 2026-10-04. Counts are
observations, not frozen README guarantees. No duplicate mapping capabilities added.

Refresh inventories/NEXT/demo after behavior is stable; use make index deliberately; test actual routes and selection wording; avoid duplicate mapping capabilities.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A04-07 — Cross-process cache/resume is a missing convenience, not a prerequisite for a small first release

docs/usage.md now explicitly states run-local caching, no cross-process resume/checkpoint command, arq queue versus braid state, and custom cache protocol limits. Persistence remains a separate feature requiring freshness/restart semantics; the new archive is not advertised as a checkpoint.

Status: deferred for first publication; scope documented.

Defer durable cache/resume until cache correctness/freshness contract is fixed; describe run-local caching for first release; track persistence as later feature.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## Completion record

Record per finding: reproduction result, changed files, tests/commands, remaining risks, status (fixed / rejected with evidence / deferred with reason / awaiting decision). Do not mark this whole audit complete while requirements remain unresolved.
