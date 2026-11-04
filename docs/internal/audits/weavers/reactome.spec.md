# Reactome proposed specification

Status proposed; [audit](reactome.audit.md).

| ID | Required behavior/acceptance |
|---|---|
| WV-REACTOME-001 | Positive cap and endpoint configuration correctly distinguish result identities; incompatible cached displays cannot be reused. |
| WV-REACTOME-002 | Expected malformed JSON/schema becomes ERROR; genuine empty pathway set remains NO_MATCH. |
| WV-REACTOME-003 | Direct multi-chunk details preserve successful chunks, isolate failed chunks and attempt later work. |
| WV-REACTOME-004 | Conditional hierarchy/participants expose source-backed stable identities and typed relations with explicit limits. |
| WV-REACTOME-005 | Configured composition, typo rejection, client ownership and safe regeneration follow shared accepted policy. |
| WV-REACTOME-006 | Species/inference/release semantics documented and relevant observed evidence retained; conflict policy deterministic. |

Retain membership capability IDs and full fan sets. Cohort enrichment/expression and
species comparison remain deferred as separate contracts. Runtime/manifest fixes bump
all version sites and selectively regenerate; no core biological assumptions.

Compatibility clarification (2026-10-08): the user permits necessary breaking changes.
Earlier preservation/default recommendations are revisable; prioritize correct, truthful
contracts and document affected interfaces, migration and version updates. Feature
proposals remain scope decisions. See the [issue hierarchy review](issue-hierarchy.md).
