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
