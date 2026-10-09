# Reactome proposed implementation plan

Status proposed; [spec](reactome.spec.md).

| Package | Requirements | Work |
|---|---|---|
| WP-REACTOME-01 | 001, 002, 003 | Explicit cap identity, source-shape validation and per-chunk detail outcomes; cache/permuted/malformed/direct large-batch cases. |
| WP-REACTOME-02 | 005, 006 | Shared construction/lifecycle, scientific membership/inference docs and safe extension guidance. |
| WP-REACTOME-03 | 004, conditional | Research exact hierarchy/participant payloads, choose groups or connected list/describe capabilities, then implement small source-local adapters/pure projections. |

Correctness first; keep analysis service expansion separate. Accepted issues before
implementation. Strict/package tests/lint and live E2E after API changes; versions,
catalogs and core floors consistent. No pushes, releases or full database downloads.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #210, #211. Pathway-list and detail responses must be lists of objects with stable identifiers. Malformed data becomes an error; a genuine empty pathway list remains a miss. Detail-request failures affect only that request chunk, and later chunks are still attempted.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.
