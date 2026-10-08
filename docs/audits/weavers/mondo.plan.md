# MONDO proposed implementation plan

Status proposed. [Spec](mondo.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-MONDO-01 | 001,002 | Review mapping precision/ambiguity contract; pure candidate selection, equal-priority shuffle and exact/broad/narrow/related fixtures. |
| WP-MONDO-02 | 003,005,006 | Validated ontology/source descriptor, safe cycle traversal and group-gated query service; DAG/invalid source/query-count regressions. |
| WP-MONDO-03 | 007 | Config/docs/examples/source coverage methodology; safe regeneration. |
| WP-MONDO-04 | 004 conditional | Review direct MONDO describe and status/mapping fields; source samples, keys/manifest/goldens. |

Accepted issues before implementation. Package tests/strict/lint and live build/known query
if source ingestion changes; no obligatory large-download audit. Preserve contracts,
source binding and version sites; catalogs for manifest changes.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.
