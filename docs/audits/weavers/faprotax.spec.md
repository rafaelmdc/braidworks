# FAPROTAX proposed specification

Status proposed. [Evidence](faprotax.audit.md).

| Finding | Acceptance |
|---|---|
| WV-FAPROTAX-001 | Real NCBI binomial/rank names match source patterns faithfully; no genus/species substring false positives; reference matcher comparison. |
| WV-FAPROTAX-002 | Ordered add/subtract/intersect operations honored, no operator-as-group; chloroplast exclusions tested. |
| WV-FAPROTAX-003 | Quoted/metadata syntax and refs validated; cycles/missing refs actionable; optional rule/source evidence explicit. |
| WV-FAPROTAX-004 | Dedicated species/operator/reference tests retain goldens/contracts; documentation says putative inference, not measured activity. |
| WV-FAPROTAX-005 | Explicit config and accurate safe docs with real executions/source update guidance. |
| WV-FAPROTAX-006 | Profile before optimizing; parsed rules immutable, caching bounded and data-identity aware if added. |

Retain bundled source unmodified and notices; no scientific confidence invented. Community
abundance aggregation requires separate spec. Patch package version sites for semantics.

Compatibility clarification (2026-10-08): the user permits necessary breaking changes.
Earlier preservation/default recommendations are revisable; prioritize correct, truthful
contracts and document affected interfaces, migration and version updates. Feature
proposals remain scope decisions. See the [issue hierarchy review](issue-hierarchy.md).
