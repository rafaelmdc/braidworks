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

## Standalone ideas awaiting reconciliation

Backend availability diagnostics [#132](https://github.com/rafaelmdc/braidworks/issues/132)
are implemented and verified; see the [acceptance record](audits/backend-availability.plan.md#acceptance-record).
Acquisition progress (#131) is also verified; see its
[implementation record](audits/acquisition-progress.md). The error-system review (#133) is also complete; see the
[boundary review](audits/error-boundaries.md). The explicit-source option for #135 is implemented; see the
[coverage decision](audits/explicit-source-coverage.md). Next is generated documentation. The three smaller design ideas will receive a usefulness review before implementation.

These older issues remain open. Their titles do not establish whether later work
partially addressed them; inspect before planning or closing them.

| Issue | Topic |
|---|---|
| [#112](https://github.com/rafaelmdc/braidworks/issues/112) | Strand declaration decorators |
| [#86](https://github.com/rafaelmdc/braidworks/issues/86) | Workflow consolidation |
| [#67](https://github.com/rafaelmdc/braidworks/issues/67) | Generated capability documentation |
| [#64](https://github.com/rafaelmdc/braidworks/issues/64) | Shared-key registry storage |

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
