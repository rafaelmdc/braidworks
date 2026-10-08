# PDBe proposed implementation plan

Status proposed. [Spec](pdbe.spec.md).

| Package | Requirements | Work |
|---|---|---|
| WP-PDBE-01 | 001 | Choose parameter versus immutable backend policy for display limit; validate; regression for cache source/limit separation. |
| WP-PDBE-02 | 002, 003 | Source-local decoding/correlation helpers and per-chunk outcomes; adverse payload and chunk cases, no generic hierarchy. |
| WP-PDBE-03 | 005, 006 | Configured construction/lifecycle aligned with accepted shared policy; docs/spec comments and safe regeneration. |
| WP-PDBE-04 | 004, 007, conditional | Research observed chain/quality schemas; specify optional groups, implement pure projections with tie/order tests and known-truth live cases. |

01–02 before feature work; 03 may share common lifecycle decisions from synthesis.
Create accepted work-package issues before coding; preserve contracts, patch package
versions consistently, verify strict + package tests + lint and live E2E after API
changes. Catalogs after manifest changes; installed/minimum-floor checks if imports
or packaging change. No push/publication.
