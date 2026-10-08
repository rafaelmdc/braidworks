# GTDB proposed specification

Status proposed. [Evidence](gtdb.audit.md).

| Finding | Acceptance |
|---|---|
| WV-GTDB-001 | Shuffled metadata gives identical results; conflicting genome classifications retained/represented under explicit reviewed selection policy. |
| WV-GTDB-002 | Unrelated search results never become confident exact lookups; ambiguity/order policy explicit and stable. |
| WV-GTDB-003 | Pair reduction validates source tree/release identity; disconnected paths explicitly incomparable, never arbitrary scientific distance. |
| WV-GTDB-004 | Metadata and tree bundle refers to one pinned release with usable source identity; custom inputs cannot inherit unrelated live release label. |
| WV-GTDB-005 | Complete replacement removes stale entries and preserves original on failure; validation checks full required schema. |
| WV-GTDB-006 | Trees validate syntax/completion and finite usable branch assumptions before publication; invalid inputs produce actionable values/errors. |
| WV-GTDB-007 | Ingestion avoids all-row intermediate list; memory/time characterized with representative bounded fixture and documented real-data target. |
| WV-GTDB-008 | Known config honored, invalid config rejected, bounded source calls and owned-client lifecycle; identity includes semantics. |
| WV-GTDB-009 | Accurate safe docs; conditional genome/release/quality fields bridge source workflows without pretending to classify novel genomes. |

Review taxonomy/geometry compatibility before changing public contract. Preserve source
binding and reopen guards. No embedded GTDB-Tk, full genome download, arbitrary cross-tree
normalization or core biological types. Version all three sites for accepted behavior.
