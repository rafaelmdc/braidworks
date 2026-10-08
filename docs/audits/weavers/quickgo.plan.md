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
