# Wikipedia proposed implementation plan

Status proposed. [Spec](wikipedia.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-WIKIPEDIA-01 | 001,002,003 | Review metric compatibility/default migration; pure effective measurement scope shared by identity/window/query/build, month mismatch and API/local parity fixtures. |
| WP-WIKIPEDIA-02 | 004,005 | Validated per-title adapter/reducer, bounded distinct calls, explicit config/lifecycle; malformed/sibling/pacing/cancellation cases. |
| WP-WIKIPEDIA-03 | 006,007 | Validated streaming source/checksum/coverage and honest title/docs/examples; tiny dump/source fixture, no forced GB download. |
| WP-WIKIPEDIA-04 | 007 conditional | Review monthly series/project/agent/access/window params with coherent title provenance; source samples/manifest/goldens. |

Accepted issues before coding; tests/strict/lint and bounded live known article after API
edits. Keep conformance/source-binding and streamed build; versions/floor/catalogs updated
as needed. Cache/resume and large historical aggregation remain separately reviewed.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #292. Pageviews responses must contain an items list with non-negative integer view counts. A returned monthly row with zero views is valid data; an empty items list is a miss. A missing/malformed items envelope is an error rather than a fabricated zero. Records retain the original query, including extra fields and whitespace.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.

## Shared coverage work implemented

The #151 findings are implemented and verified in
[SH-04 implementation and migration evidence](SH-04.implementation.md).
Other work packages in this source plan remain separately tracked.

## Shared source identity work implemented

The #154 findings are implemented and verified in
[SH-07 implementation and migration evidence](SH-07.implementation.md).
Related work packages/findings remain separately tracked.
