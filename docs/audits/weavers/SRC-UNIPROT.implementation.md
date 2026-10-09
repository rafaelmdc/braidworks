# SRC-UNIPROT — mapping composition and adverse verification

Group #158; branch `refactor/uniprot-mapping-jobs`.

| Finding | Issue | Result |
|---|---|---|
| WV-UNIPROT-007 | #186 | Private composed MappingJobClient separates submit/poll/page transport from backend routing and pure page normalization. Source-job failures remain isolated; paired siblings are cancelled and drained on failures or cancellation. |
| WV-UNIPROT-010 | #189 | Adverse lifecycle, budgets, malformed/repeated pages, timeouts, correlation, duplicate/distinct batching, cancellation and later-target recovery are tested. Five observed real accessions strengthen the existing order contract. Live exact unreviewed identity is verified. |
| WV-UNIPROT-009 | #188 | Optional exact-accession description with sequence/annotation evidence versus proteome enumeration remains pending feature scope selection. No new capability is claimed. |

## Design and behavior

The adapter borrows the backend's existing paced client; it owns no transport or
client lifetime and introduces no generic job framework, repository layer, public
records or new core assumptions. Shared private validation helpers avoid importing
the backend into the adapter. `normalize_mapping_page` is a pure source-local
function that validates requested-ID correlation and returns distinct ordered IDs
without modifying its input. Search/representative policy stays in the backend.

Default submission, status and result endpoints, reviewed-first mapping order,
result page size, polling/page budgets, batching, output groups and public builder
signatures remain unchanged. Polling has a finite 60-attempt limit, not a guaranteed
60-second wall-clock deadline: pending delays, HTTP time and pacing are additive.
The 1,000-page limit and repeated-link guard remain; a malformed next link now
fails explicitly rather than silently treating a partial result as complete.

A failed source database does not fail another source group. Separate requested
target calls recover independently after failures. A single multi-target request
remains atomic: a failed required target does not produce incomplete successful
fields or a fabricated total. Cancellation/programming errors propagate unchanged.
Reviewed/full paired jobs cancel and drain unfinished siblings before returning;
no abandoned HTTP work remains after a failed pair.

## Verification and migration

Twenty new offline cases cover pure normalization/no mutation, failed-ID correlation,
RUNNING/QUEUED/NEW poll limits, explicit failed jobs, repeated/budget/malformed pages,
invalid JSON, HTTP timeout, pending-to-finished transition, multi-ID bulk requests,
duplicate positional projection, expected/programming/cancellation pair cleanup and
later target recovery. Existing cache request-order/SQLite parity, representative
identity and source-group isolation cases remain intact.

The shared order contract now receives five observed successful accessions, including
unreviewed human A0A087WT22 and mouse P02340. Minimal real REST projections were
observed on 2026-10-09; no full source data archive was added. Contract/conformance
checks are unchanged. The live unreviewed check asserts identity values while
respecting the existing always-emitted identity group.

UniProt package tests pass: 90 passed, 10 live tests skipped by default. All ten live
checks pass when enabled, including GeneID/Ensembl/STRING mapping, reverse mapping,
misses, reviewed species-pinned identity and exact unreviewed identity. Strict spec,
conformance/golden verification passes. Full workspace lint and tests pass: 1967 pytest tests plus five unittest tests,
54 skipped. The final UniProt package rerun and strict gate also pass after
reducing observed fixtures to the fields actually used. git diff --check passes. Core APIs/floor are unchanged; package/spec/selectively regenerated
vocab agree at 0.2.9, lockfile and network catalog are updated. Supported callers
need no migration. No feature #188, publishing or persistent cache/resume work is
included.

Provider model and request workflow background:
[UniProt's API paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12230682/).
Acceptance here is proven by local regressions and live endpoint results, not by
assuming documentation alone certifies current upstream behavior.
