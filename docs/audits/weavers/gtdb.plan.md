# GTDB proposed implementation plan

Status proposed. [Spec](gtdb.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-GTDB-01 | 001,002 | Agree crosswalk and search ambiguity contract; source-local pure stable correlation, shuffled/conflicting genome fixtures and unrelated search rejection. |
| WP-GTDB-02 | 003,006 | Specify compatible path identity and disconnected behavior; validate Newick/tree assumptions, test same-tree math, mixed releases and invalid syntax. |
| WP-GTDB-03 | 004,005,007 | Pinned release bundle, provenance and validation; stream fresh staged crosswalk; atomic replacement, rollback/mismatch and memory characterization. |
| WP-GTDB-04 | 008,009 | Explicit configured assembly, bounded API ownership; docs/CLI tree usage and safe extension procedure. |
| WP-GTDB-05 | 009 conditional | Review genome accession/quality/release/synonym outputs; source samples, manifest/bridge keys, golden examples. |

Accepted implementation issues before coding; retain tests/conformance/source-change
guards. Per-package tests, strict, lint and live E2E for API changes; version sites/floor
and regenerated catalogs as required. New public boundary types round-trip JSON. Do not
replace working shared dispatch or invent generic source repositories.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.

## Shared replacement implementation

WV-GTDB-005 implemented locally as part of shared #152. Direct builds
reuse core ensure_local_db staging/lock/validation/publication, replacing the
complete reference database and preserving previous targets on failure. Version
0.2.4; other findings and work-package portions remain proposed.

Validation: 58 passed, 2 live tests skipped; strict conformance/golden and lint
passed. Regression tests cover stale taxon/species removal, incomplete query
schema rejection and iterator/empty-input/release/publication failures with and
without existing targets. Release bundle coherence and ingestion memory work
(WV-GTDB-004/007) remain open. No API backend changes.

## Shared source identity work implemented

The #154 findings are implemented and verified in
[SH-07 implementation and migration evidence](SH-07.implementation.md).
Related work packages/findings remain separately tracked.

## SH-08 identity implementation

Primary shared identity findings are implemented under #155; see
[SH-08 implementation and validation](SH-08.implementation.md). Source-specific
work packages with additional feature proposals remain tracked by their own groups.
