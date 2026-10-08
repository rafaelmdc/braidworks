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
