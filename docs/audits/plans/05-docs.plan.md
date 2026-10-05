# Audit 05 fix plan

Spec: ../specs/05-docs.spec.md. Status: implementation completed except explicitly deferred findings. See ../README.md for final validation and delivery status. Never count a source-only report as a passing regression.

## A05-01 — The recommended next task is already implemented

Status: fixed.

Replaced docs/NEXT.md with current publication gates and corrected docs/weaver-roadmap.md priority. Existing UniProt bidirectional mapping and browser execution animation are explicitly shipped. Historical upstream failures dated rather than asserted current. Old NEXT retained in local scratch only.

Rewrite NEXT from current acceptance gaps; date historic observations; do not duplicate shipped bridge.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A05-02 — Published weaver inventory is incomplete and stale

Status: fixed.

Catalogue regenerated from all 17 specs/33 capabilities; keys and offline network
view regenerated from current manifests. Added docs/sources.md covering every source,
network/bundled/local prerequisites, default discovery versus configured builders,
large optional acquisitions, representative semantics and citations. Replaced obsolete
stub instructions in GMrepo/MONDO/Wikidata/Wikipedia READMEs, and corrected Disbiome's
claim that CLI discovery builds its DB. Setup details checked against factories and
setup functions; no large data acquisition performed.

Regenerated docs/weavers-index.tsv and docs/keys-index.md: 33 capabilities across all 17 weavers. Catalogued existing wikidata.sitelinks leaf description; regeneration has no uncatalogued-field warning. README labels its table as selected sources, roadmap table labels historical/proposed interfaces. Detailed per-source setup documentation still needs review.

Regenerate full catalogue after manifests stabilize; label README selection; verify every source and setup prerequisite.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A05-03 — Root README contains an obvious generated markup artifact

Status: fixed.

Removed leaked closing markup from root README; inspected ending and git diff --check.

Remove literal leaked closing tags; inspect rendered document ending.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A05-04 — Core package dependency description is inaccurate, and package install guidance is incomplete

Status: fixed.

Corrected core/toolkit dependency descriptions. docs/installation.md supplies a
selected molecular environment, full workspace, browser extra and standalone wheel
instructions without claiming unconfirmed PyPI availability. Actual selected sync,
CLI path and live UniProt->PDBe query pass. All 20 packages carry repository/docs/issues
URLs and package-index-safe hosted README links. Artifact metadata/install checker
verifies these URLs and source resources. Channel publication belongs to A02-04.

Core README now accurately names networkx and platformdirs; root README no longer calls toolkit base install stdlib-only. Actual all-package wheel installation rehearsed; package-friendly hosted documentation/install channel guidance remains open.

Correct dependency description; document supported standalone install set after artifact rehearsal; provide hosted/repository links suitable for package users.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A05-05 — User docs promise complete, mutually exclusive outcomes and fan-out without qualifying known limits

Status: fixed.

Following A01-04/05 regressions, docs/index.md distinguishes terminal fatal_errors from recovered diagnostic history; usage/fanout docs describe leaf budgets, truncations and current ambiguity safeguards. No unlimited-expansion or disjoint-errors claim remains in this user entry page. Default review semantics are now approved and shipped under A01-03.

Follow A01-04/A01-05 repairs; update accounting and truncation examples only after regression tests; retain intended guarantees rather than hiding defects in prose.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## A05-06 — Documentation map mixes audiences and fails to identify a current user path

Status: fixed.

Reorganized docs/index.md into first-run user path, task recipes/reference, contributor
internals and explicitly historical designs. README links installation/source setup;
usage identifies environment activation/no-sync behavior. Local file and Markdown
anchor scan checks 339 targets across 69 documents, including same-repo hosted README
links mapped to the checkout; no missing targets. External deployment/availability
is not certified. Demo shell syntax and actual live demo pass.

Organize tutorials/recipes/reference/contributor docs; label historical plans; verify local links/anchors and runnable examples.

Acceptance: fulfill this finding’s source-spec validation criteria with recorded commands/results; update any stale evidence or rejected hypothesis. Keep compatibility by default, and document deliberate contract changes.

## Completion record

Record per finding: reproduction result, changed files, tests/commands, remaining risks, status (fixed / rejected with evidence / deferred with reason / awaiting decision). Do not mark this whole audit complete while requirements remain unresolved.
