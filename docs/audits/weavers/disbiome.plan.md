# Disbiome proposed implementation plan

Status proposed. [Spec](disbiome.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-DISBIOME-01 | 001,005 | Review exact/rank/ancestor input contract, correct manifest/backend/docs, real routed genus/species fixtures and CLI usage. |
| WP-DISBIOME-02 | 002,003,004 | Validated build manifest/provenance; source-local query/projection gating, compact evidence IDs and measured cost tests. |
| WP-DISBIOME-03 | 003,006 conditional | Review disease→microbe bridge and evidence filters; observed samples, parameters/fan keys/goldens. |

Accepted issues before coding; package tests/strict/lint and bounded live build/known query
when acquisition changes. Preserve SourceBinding/contracts and raw full records; patch
versions/core floor and catalogs as needed. No mandatory new repository hierarchy.
