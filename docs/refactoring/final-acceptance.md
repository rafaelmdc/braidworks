# Local programme acceptance

Date: 2026-10-08. Status: W14 verified locally; remote delivery and publication deferred.
Branch: `refactor/persistence-foundations`. Programme: #146; remote delivery remains open.

## Accepted scope

The three audit rounds have local implementation evidence: readiness baseline RD01–08,
persistence PF01–07, application AP01–07, and the conditional AP08 assessment.
[A08's documented decision](ncbi-dispatch-assessment.md) retains the NCBI custom runtime;
no adapter or domain-specific core extension is introduced. Publishing/release activation
(#142) remains explicitly deferred. This report does not authorize pushing or merging.

## Verification matrix

| Gate | Outcome | Evidence |
|---|---|---|
| Complete workspace suites | 1,481 passed, 48 skipped; release-tool unittests 5 passed | `.audit-local/w14-tests.log` |
| Workspace lint and changed-file formatting | Passed | `.audit-local/w14-lint.log`; Ruff format check |
| Strict weaver verification | All 17 passed, including goldens and placeholder checks | `.audit-local/w14-strict.log` |
| Current wheel/sdist distribution | All 20 package pairs built and passed metadata/resource, Twine and clean-install smoke | `.audit-local/w14-build.log`, `w14-artifact-check.log`, `w14-twine.log` |
| Minimum-core weaver compatibility | All 17 current weavers passed fixture goldens at actual declared core 0.1.8, 0.13.0 or 0.13.3 | `.audit-local/w14-floor-check.log` |
| Installed toolkit scaffolding | Six lookup/resolver/bulk/API-key variants generated, parsed/compiled, imported and matched manifests at exact core 0.21.0; strict TODO refusal preserved | `.audit-local/w14-scaffold.log` |
| Generated persistent Python | Runs with core wheel alone, without toolkit/FastAPI; duplicate rows saved | `.audit-local/w14-core-only.log` |
| Installed browser usability | Passed after final fixes: graph/typed routes, recipes, code, exports, dropped stream/retry, review and native keyboard focus | `.audit-local/w14-browser-baseline-installed.log` |
| Installed browser continuation | Passed after final fixes: recipe settings, checkpoint cancellation, saved immutable settings and explicit candidate approval | `.audit-local/w14-browser-installed.log` |
| Browser batch/encoder parity | Paste/CSV upload, duplicate source identity, cancel/retry, typed/graph encoder equality and repeated traversal passed | `.audit-local/w14-browser-batch.log`, `w14-browser-encoder.log` |
| Generated catalogs | Regenerated weaver and key indexes match tracked outputs byte for byte; no manifest/catalog changes needed | `.audit-local/w14-index.log`, temporary outputs compared with `cmp` |
| Documentation/workflows | Local links/anchors and actionlint passed; current inventories match | `.audit-local/w14-links.log`, `w14-workflows.log` |

Latest runtime versions: **core 0.21.0**, **toolkit 0.6.3** (core>=0.21.0),
**arq 0.2.1** (core>=0.13.0). Weaver versions are unchanged by A06–A08/W14.
Arq's clean minimum-core installation without HTTPX was separately verified in
`.audit-local/a07b-installed.log`; Redis authentication/authorization failures do not retry.

## Regressions found during final rehearsal

The wider real-browser journey found two gaps missed by the earlier narrow checks:

1. `showCode` used a removed `have` variable after a successful API response, preventing
   the generated-code dialog from opening. It now reads the canonical request's inputs;
   the same request drives the placeholder reminder and artifacts.
2. Typed planning while graph mode remained active allowed its Run button to read graph
   inputs/traversals instead of the displayed typed route. Typed planning now leaves graph
   mode, aligning displayed controls, run inputs and exports.

Both fixes are in toolkit 0.6.3. The local Firefox baseline passed generated code with
real/placeholder inputs, native focus trapping/Escape restoration, typed export identity,
recipe restoration, review/confidence, and invalid-parameter retry. Its dropped-stream
probe was updated from obsolete EventSource interception to the current fetch/SSE stream;
that is a rehearsal adaptation, not a product behavior change. The clean installed-wheel
repeat passed both the complete baseline and persistence/review journeys.

## Evidence boundaries and delivery

Checks ran on Linux/Python 3.12 with isolated dependencies and temporary clean-install
and Firefox profiles. No biological data downloads, system dependency installations,
source API changes, tags, pushes, merges or publication were performed in final acceptance.
Temporary environments and browser/server processes are cleaned up by the harnesses.
`.audit-local` artifacts and logs remain untracked and excluded from commits.

Opt-in live source and real Redis tests remain skipped; Windows lock behavior and remote
CI/fleet/deployment were not exercised here. These checks establish the specified local
acceptance gates, not fresh upstream availability, broker or release certification.
Prevalidated scaffold writes remain nontransactional; resume may repeat an interrupted
wave while preserving saved-state revision/ownership rules. See persistence/scaffold
specifications for those deliberate limits.

A08 assessment commit: `b5f9d8f`; final browser fix commit: `98bfd83` (local, unpushed).

Implementation evidence: [combined plan](implementation.plan.md),
[application plan](application.plan.md), [persistence plan](persistence.plan.md),
[readiness plan](readiness.plan.md). Delivery issues remain open until remote delivery;
#133's broader error-system redesign and #142's publication choices stay outside this scope.
