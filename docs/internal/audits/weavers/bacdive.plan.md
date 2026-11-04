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

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #243. Taxon-search HTTP 400/404 is a miss. A failed /fetch request for identifiers already returned by the source is an error, including 404. Taxon IDs, page envelope and returned strain records are validated; missing phenotype measurements remain legitimate sparse data. The first-type-strain and scan-cap policies are unchanged and remain separate coverage/selection work.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.

## Shared coverage work implemented

The #151 findings are implemented and verified in
[SH-04 implementation and migration evidence](SH-04.implementation.md).
Other work packages in this source plan remain separately tracked.

## Shared batching/acquisition work implemented

The #153 findings are implemented and verified in
[SH-06 implementation and configuration evidence](SH-06.implementation.md).
Other work packages/findings in this source plan remain separately tracked.

## SH-08 identity implementation

Primary shared identity findings are implemented under #155; see
[SH-08 implementation and validation](SH-08.implementation.md). Source-specific
work packages with additional feature proposals remain tracked by their own groups.

Shared configuration/lifecycle findings in #149 are implemented; see
[SH-02 acceptance, verification and migrations](SH-02.implementation.md).
Source-specific remaining proposals and capabilities stay separately tracked.
