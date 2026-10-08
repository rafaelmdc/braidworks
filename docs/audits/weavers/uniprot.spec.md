# UniProt proposed specification

Status: proposed, not accepted/implemented. [Evidence](uniprot.audit.md).

| Requirement | Intended behavior | Acceptance |
|---|---|---|
| WV-UNIPROT-001 | Explicit accession retains exact identity regardless of review status; organism mismatch cannot select another accession | Reviewed/unreviewed exact IDs, unknown ID and species mismatch exercise explicit policy |
| WV-UNIPROT-002 | Mapping sets distinct and stable; reviewed class first, explicit stable ordering within each class; count reflects normalized records | Duplicate/permuted/multi-page fixture results give identical unique IDs and counts |
| WV-UNIPROT-003 | Each computed output group corresponds to completely fetched target data; count/record-only requests have documented semantics | Shared executor cache GeneID→PDB and reverse request order both perform required work; SQLite parity; count-only never fabricated miss |
| WV-UNIPROT-004 | Expected response decoding/schema failures are error values, isolated to affected query/job; programming/cancellation errors not broadly swallowed | Invalid JSON, null/malformed rows, missing jobId and malformed pagination report explicit errors with preserved batch shape |
| WV-UNIPROT-005 | Endpoint-specific status handling follows repository convention | Invalid/not-found search versus job/service failures have meaningful tested results |
| WV-UNIPROT-006 | Public configured builder forwards supported settings, rejects typos, and defines owned/borrowed client closing and source identity | Injection through provider works; owned client closes once; borrowed remains usable; distinct sources cannot share cache identity |
| WV-UNIPROT-007 | Mapping-job transport is composed separately from pure result normalization; errors isolated per source/target grouping | Later good group remains good after another job fails; polling/page limits and cancellation verified |
| WV-UNIPROT-008 | Docs make accurate identity/isoform/evidence promises and safe regeneration instructions | Examples executable; three capabilities documented; no force-preservation claim |
| WV-UNIPROT-009 | Optional accession description emits sequence and structured annotation evidence where available | Requires separately accepted fields, groups, limits and representative raw samples before coding |
| WV-UNIPROT-010 | Tests cover mapping lifecycle and scientific identity cases | Meaningful adversarial fixtures and live known-truth exact unreviewed/representative mapping examples |

Preserve public capability IDs and existing output types unless a documented migration
is accepted. Output-group changes affect cache coverage and query recipes; bump package
in all three sites and document invalidation. Reuse current core APIs; raise floor
only where actually needed. Do not regenerate over implemented backend files.

Feature 009 is proposed separately from correctness fixes. Proteome enumeration,
peptide/PTM/variation integration and automatic resolver conversion remain deferred
pending scope decisions. No generic async-job framework or domain logic in core.
