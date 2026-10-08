# GMrepo proposed implementation plan

Status proposed. [Spec](gmrepo.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-GMREPO-01 | 001,002,003,004 | Validated normalization, stable correlation and acquisition/build coverage manifest; failed/capped/empty/duplicate/numeric fixtures. |
| WP-GMREPO-02 | 006,007 | Composed summary/profile acquisition, explicit concurrency/pacing budget/config; honest docs/current source samples and measured group-cost projection. |
| WP-GMREPO-03 | 005 conditional | Review run/project details/cohort filters and disease bridges; source samples/keys/manifest/goldens. |

Accepted implementation issues before coding; package tests/strict/lint and existing
bounded live mini-build for acquisition changes, not full multi-thousand-call crawl.
Preserve contracts/source binding; version/floor/catalog updates as needed. Incremental
profile extension, cache/resume and downstream statistics require separate review.
