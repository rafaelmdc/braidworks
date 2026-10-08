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
