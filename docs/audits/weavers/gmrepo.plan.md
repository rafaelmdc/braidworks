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

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.

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

## Source correctness acceptance

#271 is implemented; see [gmrepo implementation and validation](SRC-GMREPO.implementation.md). Other work packages remain separately tracked.
