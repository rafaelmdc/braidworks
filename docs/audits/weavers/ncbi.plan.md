# NCBI proposed implementation plan

Status proposed. [Spec](ncbi.spec.md).

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
