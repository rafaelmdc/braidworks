# QuickGO proposed implementation plan

Status proposed. [Spec](quickgo.spec.md).

| Package | Requirements | Work |
|---|---|---|
| WP-QUICKGO-01 | 001, 003 | Validate page/row identity in common single/bulk projection; source-local pure correlation and coverage helpers; adverse data/echo and cancellation cases. |
| WP-QUICKGO-02 | 002, 006 | Define semantic budget/source identity and configured ownership; prove cache budget separation, document partial batch behavior and repair docs. |
| WP-QUICKGO-03 | 004, conditional | Accept specific filters/defaults; validate declared params, API semantics and raw-evidence preservation with observed examples. |
| WP-QUICKGO-04 | 005, conditional | Specify typed ontology relations/replacements and outputs; fixtures/goldens/live term cases. |

Correctness before expansion. Preserve existing coverage/evidence tests and conformance.
Accepted work issues before coding, patch package sites/core floor only as needed,
package tests + strict + lint + live E2E for API edits. Catalog regeneration for
manifest changes. Do not introduce a universal page hierarchy or enrichment engine.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #205. Annotation/term rows and pagination metadata are validated before projection. Missing pagination metadata still means unknown coverage, with the existing exported warning. The observed empty-source convention (zero hits, current=total=0) remains a clean miss. An explicitly echoed different accession/page or unrequested term is an error. Term-detail chunk failures preserve other chunks. For legacy singleton responses without geneProductId, correlation still relies on the single requested accession; present echoes are checked.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.
