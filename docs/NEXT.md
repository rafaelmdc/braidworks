# Current project decisions and backlog

Updated 2026-10-15. Completed readiness/refactoring and approved weaver work have
been pushed to the review branch; they have not been merged or published. Historical
plans remain in [design history](history.md). This page summarizes the open queue,
not the instructions for using Braidworks.

## Decisions deliberately left open

| Work | Status |
|---|---|
| [Publication channel and release activation (#142)](https://github.com/rafaelmdc/braidworks/issues/142) | Deferred. Checkout/wheel installs are documented; package publication needs the owner's release decision. |
| [Further cache/resume scope (#143)](https://github.com/rafaelmdc/braidworks/issues/143) | Deferred follow-up. Opt-in SQLite caches, saved runs, and human continuation interfaces already exist; see [persistence](persistence.md). |
| [GTDB cross-tree distance semantics (#234)](https://github.com/rafaelmdc/braidworks/issues/234) | Deferred. Tree identity/distance changes need a deliberate design decision. |

The [GTDB parent (#165)](https://github.com/rafaelmdc/braidworks/issues/165) and
[weaver programme (#147)](https://github.com/rafaelmdc/braidworks/issues/147) remain
open for the deferred GTDB finding.

## Platform cleanup loop

The eight-issue loop is resolved. Work is on pushed branches, without merge or
publication. Each later branch includes the preceding changes.

| Issue | Resolution | Branch / record |
|---|---|---|
| [#132](https://github.com/rafaelmdc/braidworks/issues/132) | Implemented backend diagnostics | `feat/backend-availability-diagnostics`; [acceptance](audits/backend-availability.plan.md#acceptance-record) |
| [#131](https://github.com/rafaelmdc/braidworks/issues/131) | Implemented acquisition progress/socket limits | `fix/acquisition-progress`; [record](audits/acquisition-progress.md) |
| [#133](https://github.com/rafaelmdc/braidworks/issues/133) | Fixed status classification; retained existing error boundaries | `fix/error-classification`; [review](audits/error-boundaries.md) |
| [#135](https://github.com/rafaelmdc/braidworks/issues/135) | Implemented explicit AGORA universe; automatic pruning rejected | `feat/agora-taxid-universe`; [decision](audits/explicit-source-coverage.md) |
| [#67](https://github.com/rafaelmdc/braidworks/issues/67) | Generated exact inventories and CI drift checks | `feat/generated-capability-docs`; [record](audits/generated-capability-docs.md) |
| [#86](https://github.com/rafaelmdc/braidworks/issues/86) | Consolidated validation; gated automatic tags | `ci/consolidate-validation`; [record](audits/workflow-consolidation.md) |
| [#112](https://github.com/rafaelmdc/braidworks/issues/112) | Not planned after reviewing current declarations | [Decision](audits/declaration-storage-decisions.md#112--strand-decorators-not-planned) |
| [#64](https://github.com/rafaelmdc/braidworks/issues/64) | Not planned after reviewing current vocabulary storage | [Decision](audits/declaration-storage-decisions.md#64--key-database-not-planned) |

The final branch, `docs/declaration-storage-decisions`, contains the full loop.
No runtime decorator or key-database feature was added for the two rejected ideas.
They can be reopened with a concrete workflow that changes the assessment.

## Documentation review

[First-pass readability work (#299)](https://github.com/rafaelmdc/braidworks/issues/299)
reorganizes onboarding and current guides. The [accuracy follow-up (#300)](https://github.com/rafaelmdc/braidworks/issues/300)
reconciles active source summaries and generated catalogues; see the
[accuracy findings](audits/documentation-accuracy.md). The [Diátaxis map](audits/documentation-diataxis.md)
identifies remaining organization work. Three [researcher tutorials](index.md#learn-through-a-tutorial)
cover protein structures, microbial functional evidence and disease associations.
Result/storage reference is separate from tasks and explanation. Toolkit/core/source
entry pages and pacing/local-data guides now link their detailed reference homes.
The three lessons remain provisional. Final researcher examples and joint reader
testing are deferred until platform work settles; see the
[Diátaxis implementation record](audits/documentation-diataxis.md#third-implementation-increment).

For release checks use [release rehearsal](releasing.md). For evidence of delivered
work use [weaver acceptance](audits/weavers/remaining-features.plan.md) and
[refactoring acceptance](refactoring/final-acceptance.md). Local verification does
not replace remote CI or a production distributed-deployment rehearsal.
