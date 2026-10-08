# AGORA proposed implementation plan

Status proposed. [Spec](agora.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-AGORA-01 | 001,003 | Define coverage/resource availability and mapper completion; real invalid/missing/malformed-model fixtures and requested-only groups. |
| WP-AGORA-02 | 002,005 | Composed model artifact service reusing safe staging/lock patterns; parsed validation/content references; replacement/build manifest/annotation provenance and cleanup. |
| WP-AGORA-03 | 006,007,008 | Explicit builders, detached dataset projection, accurate docs/model execution and restricted-license rendering review; measured SQL/XML characterization. |
| WP-AGORA-04 | 004 conditional | Review model list/describe and bridge keys; observed samples, manifest/goldens/catalog updates. |

Accepted issues before coding; package tests/strict/lint, opt-in individual-model live
E2E if acquisition changes. No multi-GB live download gate without deliberate need.
Preserve conformance and explain behavior-specific test changes; bump version sites/floor
as needed. No cache/resume implementation in this proposal.
