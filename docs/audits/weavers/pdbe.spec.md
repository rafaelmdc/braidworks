# PDBe proposed specification

Status: proposed. [Evidence](pdbe.audit.md).

| ID | Requirement and acceptance |
|---|---|
| WV-PDBE-001 | Positive display limit and endpoint configuration included in result identity; different limits/source endpoints cannot reuse incompatible cached results. Prefer declared query limit if humans need it. |
| WV-PDBE-002 | Expected malformed JSON/schema produces ERROR; valid empty response remains NO_MATCH; unrelated rows never assigned to absent IDs. |
| WV-PDBE-003 | Multi-chunk direct fetch preserves good chunks and attempts later chunks after a failed/not-found chunk. |
| WV-PDBE-004 | Conditional new groups retain chain/entity/range and quality information from real observed payloads; existing leaves stay compatible. |
| WV-PDBE-005 | Explicit construction, typo rejection and owned/borrowed client lifecycle; safe contributor regeneration. Shared requirements referenced, not counted twice. |
| WV-PDBE-006 | Spec comments match bulk endpoint, docs qualify determinism and show configured execution. |
| WV-PDBE-007 | Rich chain records have stable identity/tie ordering across permuted responses. |

Preserve full fan set versus capped display and true count. Keep core domain-neutral.
Features 004/007 need accepted scope; ligand/assembly expansion deferred. Runtime or
manifest changes patch all three version sites and regenerate selectively in scratch.
