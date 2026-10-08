# Specifications and implementation programme

Programme tracker: [#146](https://github.com/rafaelmdc/braidworks/issues/146).

Date: 2026-10-05. The user accepted the direction of three audit rounds and requested
implementation specifications and plans. These documents consolidate those rounds;
they do not repeat the audits or count a proposal as completed implementation.

| Round | Implementation spec | Matching plan | Evidence/design | Delivery status |
|---|---|---|---|---|
| 1: publication readiness, six audits | [Readiness](readiness.spec.md) | [Readiness plan](readiness.plan.md) | [Six reports/specs/plans](../audits/README.md) | 43 findings fixed locally; remote delivery pending |
| 2: persistence foundations | [Persistence](persistence.spec.md) | [Persistence plan](persistence.plan.md) | [Audit](../audits/persistence-design.spec.md), [design](../audits/persistence-refactor-design.md) | P01–P07 verified locally |
| 3: application patterns | [Application](application.spec.md) | [Application plan](application.plan.md) | [Audit](../audits/application-patterns.spec.md), [design](../audits/application-patterns.plan.md) | A01–A07 verified locally; A08 conditional |

[The combined implementation plan](implementation.plan.md) defines dependencies,
commit-sized work packages and acceptance evidence. Requirement IDs below are the
implementation checklist; original Axx/Pxx/Nxx IDs remain the evidence trail.
The new specs resolve boundaries shared by the earlier proposals. If a tentative
suggestion in an audit conflicts with these contracts, use the implementation spec
and record why in the relevant issue. Repo AGENTS.md still applies.

Keep all work on `refactor/persistence-foundations`, based on the unpushed readiness
branch. No merge between these local work packages is required. Use existing issues
[#144](https://github.com/rafaelmdc/braidworks/issues/144) and
[#145](https://github.com/rafaelmdc/braidworks/issues/145) for implementation progress;
[#143](https://github.com/rafaelmdc/braidworks/issues/143) remains the cache/resume feature
acceptance tracker. Cache/resume now have a specified post-refactor workstream; their
earlier deferred status describes the first publication-readiness round, not an
instruction to implement them before their foundations are ready.

Publishing [#142](https://github.com/rafaelmdc/braidworks/issues/142) stays deferred.
No publication, pushing, merging, remote release activation or manual tags are included.

A06 scaffold work has a detailed [specification](scaffold.spec.md) and
[implementation plan](scaffold.plan.md), grounded in the current generator and tests.
