# NCBI proposed specification

Status proposed. [Evidence](ncbi.audit.md). Preserve A08 custom-runtime decision.

| Finding | Acceptance |
|---|---|
| WV-NCBI-001 | Every public build path preserves existing valid target byte-for-byte on parse/validation failure, publishes validated replacement atomically and retains source hash metadata. |
| WV-NCBI-002 | Real valid build CLI exits successfully with accurate human/JSON summary; malformed input reports actionable failure. |
| WV-NCBI-003 | Failed requested products/sequences are ERROR or explicitly partial with uncomputed failed group; never silently complete/cache them. |
| WV-NCBI-004 | Correlation handles multiple echoed genes deterministically with documented uncertainty; taxonomy candidates stable with ID tiebreak. |
| WV-NCBI-005 | Malformed/failed upstream results are values, correct per-query status and cancellation preserved. |
| WV-NCBI-006 | Config honored or rejected; endpoint/fuzzy policy identified without exposing secrets; only owned clients closed. |
| WV-NCBI-007 | Bulk retained; independent single-ID work bounded concurrent, paced, ordered and duplicate-safe. |
| WV-NCBI-008 | Cycles/budgets terminate with coverage; products pagination supported, any record cap/count semantics explicit. |
| WV-NCBI-009 | Public dataclass boundaries JSON round-trip; source-local operations/interfaces reflect actual supported responsibilities without core domain leaks. |
| WV-NCBI-010 | Accurate extension/version/docs; conditional merged/deleted and local descendants specified separately with source samples. |

Do not force ResolverRecord conversion, lose identifying review strands or weaken
conformance. Historical taxonomy redirects/local descendants require explicit scope
review; sequence downloads remain deferred. Patch versions consistently for behavior.
