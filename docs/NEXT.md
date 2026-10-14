# Current project decisions and backlog

Updated 2026-10-10. Completed readiness/refactoring and approved weaver work have
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

These older issues remain open. Their titles do not establish whether later work
partially addressed them; inspect before planning or closing them.

| Issue | Topic |
|---|---|
| [#135](https://github.com/rafaelmdc/braidworks/issues/135) | Prune expansion using downstream availability |
| [#133](https://github.com/rafaelmdc/braidworks/issues/133) | Error-system refactor |
| [#132](https://github.com/rafaelmdc/braidworks/issues/132) | Planner diagnostics for disabled backends |
| [#131](https://github.com/rafaelmdc/braidworks/issues/131) | Acquisition progress |
| [#112](https://github.com/rafaelmdc/braidworks/issues/112) | Strand declaration decorators |
| [#86](https://github.com/rafaelmdc/braidworks/issues/86) | Workflow consolidation |
| [#67](https://github.com/rafaelmdc/braidworks/issues/67) | Generated capability documentation |
| [#64](https://github.com/rafaelmdc/braidworks/issues/64) | Shared-key registry storage |

## Documentation review

[First-pass readability work (#299)](https://github.com/rafaelmdc/braidworks/issues/299)
reorganizes onboarding and current guides. The [accuracy follow-up (#300)](https://github.com/rafaelmdc/braidworks/issues/300)
reconciles active source summaries and generated catalogues; see the
[accuracy findings](audits/documentation-accuracy.md). The [Diátaxis map](audits/documentation-diataxis.md)
identifies remaining organization work. The first
[researcher tutorial](tutorials/protein-structures.md) covers protein-to-structure lookup,
interpretation and export. Two more researcher workflows and joint reader testing
remain; see the [first-pass findings](audits/documentation-readability.md).

For release checks use [release rehearsal](releasing.md). For evidence of delivered
work use [weaver acceptance](audits/weavers/remaining-features.plan.md) and
[refactoring acceptance](refactoring/final-acceptance.md). Local verification does
not replace remote CI or a production distributed-deployment rehearsal.
