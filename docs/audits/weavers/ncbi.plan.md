# NCBI proposed implementation plan

Status: WP-NCBI-01 implemented locally; remaining packages proposed. [Spec](ncbi.spec.md).

| Work package | Findings | Work and validation |
|---|---|---|
| WP-NCBI-01 | 001,002 | Extract safe staging/publication seam for direct builder and CLI; temp archive regression proves existing target survives; real CLI human/JSON checks. |
| WP-NCBI-02 | 003,005,008 | Source-local validation and page collection; carry enrichment failure/coverage through existing mapper, test requested-only group and cache completeness. |
| WP-NCBI-03 | 004 | Define gene ambiguity policy before contract change; stable correlation/candidate ordering, duplicate and shuffled response fixtures. |
| WP-NCBI-04 | 006,007 | Correct config/lifecycle/source identity; bounded single-ID concurrency retaining bulk/pacing, test request counts/order/cancellation. |
| WP-NCBI-05 | 009,010 | Boundary round trips, small operation protocols/composed source adapters as needed; correct CLI/version/extension docs without replacing custom runtime. |
| WP-NCBI-06 | 010 conditional | Separate reviewed historical-taxid/local-descendant requirements; source snapshots/fixtures/indices, manifest and registered-key changes only if accepted. |

Correctness before optional expansion. Open accepted implementation issues before
coding; per-package tests/strict/lint, live E2E for API edits, version sites and core
floor as required. Keep handwritten vocab in lockstep; regenerate catalogs for manifest
changes. Reuse safe existing acquisition/resolver ownership, avoid a second repository
layer or generic biological core abstraction. No implementation in this audit.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.

## WP-NCBI-01 implementation evidence

Issues #222 and #223: public builder stages a fresh database under the existing
BuildLock, rejects failed validation, closes SQLite before atomic replacement and
cleans staging on failure. Unified/standalone build CLI reports current summary
fields and actionable failures. NCBI version bumped to 0.2.5.

Regression coverage includes malformed nodes/names, validation and publication
failures with/without an existing target, complete successful replacement with
source digest metadata, and real subprocess CLI builds/JSON reports/errors.
Package suite: 137 passed, 11 live tests skipped. API backends unchanged.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #226. Taxonomy, genome, gene and requested enrichment responses are validated at source-local seams. Taxonomy, assembly/gene-detail and symbol request chunks preserve unrelated successes. Taxonomy HTTP 400/404 and explicitly reported invalid-identifier absence remain misses; network/service/malformed data failures are errors. The observed empty taxonomy-suggest response {} remains a miss. Failed requested lineage, sequence or product enrichment now makes the affected query an error instead of returning apparent success with silently missing requested fields. Cancellation and unrelated programming faults propagate through enrichment. API-only live checks select test_live tests; the unrestricted test-live target also acquires the large local taxonomy database.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.

## Shared coverage work implemented

The #151 findings are implemented and verified in
[SH-04 implementation and migration evidence](SH-04.implementation.md).
Other work packages in this source plan remain separately tracked.
