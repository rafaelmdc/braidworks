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

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.

## Shared replacement implementation

WV-AGORA-005 implemented locally as part of shared #152. Direct builds
reuse core ensure_local_db staging/lock/validation/publication, replacing the
complete reference database and preserving previous targets on failure. Version
0.2.3; other findings and work-package portions remain proposed.

Validation: 32 passed, 1 skipped; strict conformance/golden and lint passed.
The existing restricted-license warning remains conservative. Acquisition cleanup
is tested even when VMH retrieval fails. Annotation source/digest/count metadata
and fresh replacement are covered by regression tests. Parser releases all
processed elements rather than retaining nonreaction subtrees. Bounded offline
measurement: 1,000 / 20,000 / 100,000 species (60 KB / 1.23 MB / 6.19 MB XML) used
275,380 / 200,004 / 201,660 peak traced Python bytes and 0.011 / 0.202 / 0.985 seconds
on this laptop. See [measurement script](../reproductions/weaver_sbml_memory.py).
This measures the parser, not whole-archive/native memory; reaction rows remain
materialized per model to preserve existing malformed-model behavior. Model coverage
tracking (WV-AGORA-003) and individual-model publication (WV-AGORA-002) remain open.

## Shared coverage work implemented

The #151 findings are implemented and verified in
[SH-04 implementation and migration evidence](SH-04.implementation.md).
Other work packages in this source plan remain separately tracked.

Shared group #156 implementation and measurements are recorded in
[SH-09](SH-09.implementation.md). Source-owned capability proposals and other
work packages remain separately tracked.

Shared configuration/lifecycle findings in #149 are implemented; see
[SH-02 acceptance, verification and migrations](SH-02.implementation.md).
Source-specific remaining proposals and capabilities stay separately tracked.
