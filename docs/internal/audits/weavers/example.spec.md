# Example proposed specification

Status: proposed, not implemented. Evidence: [audit](example.audit.md).

| Requirement | Finding | Required behavior | Acceptance |
|---|---|---|---|
| WV-EXAMPLE-001 | Same ID | Safe extension instructions describe scratch generation and selective application; accurately explain force overwrite | Walk instructions on a disposable copy and preserve the implemented backend |
| WV-EXAMPLE-002 | Same ID | Empty config remains valid; unsupported builder options produce a clear structural configuration error | Zero-config/provider builds work; typo option cannot silently succeed |
| WV-EXAMPLE-003 | Same ID | Document deliberate scaffold differences, units and teaching limitations; show complete asynchronous batch execution and result handling | Run the documented example offline and observe requested-only strands plus a miss |
| WV-EXAMPLE-004 | Same ID | Contract samples use the five bundled real IDs; additional focused cases cover missing IDs, duplicates and group filtering | All five IDs identify correct traits; no reordering or unwanted output; contracts retained |
| WV-EXAMPLE-005 | Same ID | Canonical source URL identifies bundled data; spec and generated vocab agree | Strict verification and source reference rendering use the canonical URL |
| WV-EXAMPLE-006 | Same ID | Optional pure parser defines malformed-header/duplicate-ID behavior without public API growth | Focused parser cases prove the chosen rules; identical valid records |

Compatibility: retain `describe_traits`, taxid key, string output types, output groups,
manual registration and zero-config behavior. Intentional tightening of unsupported
config is documented. Patch-bump all three version sites for runtime/manifest changes;
keep core floor unchanged unless an implementation actually requires a newer API.

Do not add automatic discovery, external data sources, fuzzy resolution, generic
repository abstractions or a new public record hierarchy. Requirement 006 is optional
and may be deferred independently; other requirements await review.

Compatibility clarification (2026-10-08): the user permits necessary breaking changes.
Earlier preservation/default recommendations are revisable; prioritize correct, truthful
contracts and document affected interfaces, migration and version updates. Feature
proposals remain scope decisions. See the [issue hierarchy review](issue-hierarchy.md).
