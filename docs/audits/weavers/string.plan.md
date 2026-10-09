# STRING proposed implementation plan

Status proposed; [spec](string.spec.md).

| Package | Requirements | Work |
|---|---|---|
| WP-STRING-01 | 001, 003 | Specify stable identity bridge/migration first; source-local pure normalization and identity tie-break; same-name/different-ID and cross-species drill-down regressions. |
| WP-STRING-02 | 002, 004, 005 | Define bounded/full neighbor scope, count/coverage and supported query defaults; service release identity and cache separation. Verify documented mixed-species/>10 constraints live. |
| WP-STRING-03 | 006, 007 | Correlation/schema adapters, safe grouped failures, explicit config/lifecycle/pacing; update bulk/scientific/contributor docs. |

No cohort network/enrichment engine in these packages. Accepted actionable issues
before coding. Preserve contracts, strict and existing batching; add real source
samples, live E2E for API edits and identity known-truth tests. Package versions,
catalogs/floors consistent. No push or publication.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #220. Mapping/edge response shapes and echoed identifiers are validated. Malformed or uncorrelatable rows now produce an error for their request chunk, including nameless edges without a query identifier that were previously silently skipped. Successful mapping/partner chunks remain available. Empty lists and identifier HTTP 400/404 remain misses. This changes one existing non-contract unit test to assert the stronger failure semantics; conformance tests are preserved.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.

## Shared coverage work implemented

The #151 findings are implemented and verified in
[SH-04 implementation and migration evidence](SH-04.implementation.md).
Other work packages in this source plan remain separately tracked.

## Shared source identity work implemented

The #154 findings are implemented and verified in
[SH-07 implementation and migration evidence](SH-07.implementation.md).
Related work packages/findings remain separately tracked.
