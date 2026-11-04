# STRING proposed specification

Status proposed; [audit](string.audit.md).

| ID | Required behavior/acceptance |
|---|---|
| WV-STRING-001 | Stable partner IDs/taxon retained and drill-down cannot silently change species; duplicate names remain distinct where identities differ. Existing name output migration explicit. |
| WV-STRING-002 | Returned neighbor scope/cap and observed count labeled honestly; complete sets only claimed when established; partial fan policy explicit. |
| WV-STRING-003 | Edge dedup/order by identity and score invariant to repeated/permuted rows. |
| WV-STRING-004 | Service version/configuration represented truthfully in cache/source identity; chosen pinned release actually probed. |
| WV-STRING-005 | Conditional supported score/network/species parameters validated/defaulted; docs distinguish functional from physical evidence. |
| WV-STRING-006 | Expected malformed/uncorrelatable data becomes ERROR, not false biological absence; input order and unaffected-group success preserved. |
| WV-STRING-007 | Explicit construction/lifecycle; reliable echo/index mapping; accurate bulk/safe regeneration docs; source-recommended pacing policy assessed. |

Stable ID bridge/filter additions require scope and migration review. Dataset network
and enrichment capabilities deferred as separate cohort semantics. No binding-strength
claim or universal model/repository hierarchy. Patch version sites; core neutral.

Compatibility clarification (2026-10-08): the user permits necessary breaking changes.
Earlier preservation/default recommendations are revisable; prioritize correct, truthful
contracts and document affected interfaces, migration and version updates. Feature
proposals remain scope decisions. See the [issue hierarchy review](issue-hierarchy.md).
