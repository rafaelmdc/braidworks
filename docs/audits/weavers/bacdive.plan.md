# BacDive proposed implementation plan

Status proposed. [Spec](bacdive.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-BACDIVE-01 | 001,002,003,005 | Specify representative/coverage identity, validated source collector and pure stable projection; genus/subspecies, cap,404, malformed/conflicting measurement fixtures. |
| WP-BACDIVE-02 | 004,007 | Distinct query work with bounded concurrency and chunked fetch, explicit config/owned-client lifecycle; request-count/pacing/cancellation tests. |
| WP-BACDIVE-03 | 006,007 | Correct group/scope/default docs and safe regeneration, real Python execution example. |
| WP-BACDIVE-04 | 006 conditional | Review list_strains/describe_strain pair, registered strain/sequence bridges and source-evidence groups; source samples, strict goldens and live examples. |

Accepted work issues before coding; package tests/strict/lint/live E2E for API edits,
version sites and catalogs for manifest changes. Shared runtime remains. Cache/resume
implementation and cohort phenotype search remain separately reviewed.
