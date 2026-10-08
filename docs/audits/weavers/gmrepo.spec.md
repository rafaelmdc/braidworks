# GMrepo proposed specification

Status proposed. [Evidence](gmrepo.audit.md).

| Finding | Acceptance |
|---|---|
| WV-GMREPO-001 | Per-resource acquisition outcomes persisted; failed taxon/run never silently successful complete zero. |
| WV-GMREPO-002 | Profile cohort/cap/selected/fetched/empty/failed scope and denominator explicit; missing acquisition distinguished from biological zero. |
| WV-GMREPO-003 | Stable unique logical rows/run IDs, complete order and duplicate-safe counts. |
| WV-GMREPO-004 | Finite numeric ranges/counts/units validated with source semantics and raw invalid context. |
| WV-GMREPO-005 | Conditional run/project/QC metadata, filters and disease bridges specified from observed current source. |
| WV-GMREPO-006 | Bounded configurable polite acquisition and coverage; summary/profile resources separated without implicitly accepting resume/cache feature. |
| WV-GMREPO-007 | Accurate examples/output/source samples/config/safe regeneration and group-cost semantics. |

Preserve local generation binding, complete raw summary data and existing noncausal scope.
New keys/parameters reviewed, all version sites updated for accepted behavior.

Compatibility clarification (2026-10-08): the user permits necessary breaking changes.
Earlier preservation/default recommendations are revisable; prioritize correct, truthful
contracts and document affected interfaces, migration and version updates. Feature
proposals remain scope decisions. See the [issue hierarchy review](issue-hierarchy.md).
