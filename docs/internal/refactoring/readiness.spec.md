# Round 1 implementation spec: preserve the readiness baseline

Matching plan: [readiness.plan.md](readiness.plan.md).
Status: implemented locally. Source of truth for historical findings:
[readiness record](../audits/README.md) and its six linked specs/plans.
This round contains 45 numbered findings: 43 fixed, one publication deferral and one
cache/resume deferral. The fixed set represents 42 distinct changes because A04-01
and A03-05 describe the same export problem. Refactoring must preserve these outcomes.

| ID | Required invariant | Evidence / acceptance |
|---|---|---|
| RD01 | Cache coverage, traversal seeds, batch cardinality and result serialization remain correct | Retain original regression assertions for A01-01/02/04/07 |
| RD02 | Review/confidence, fan-out limits, backend policy and reroute references remain enforced | Retain A01-03/05/06/08 tests, including explicit truncation accounting |
| RD03 | Human interfaces preserve all terminal rows, duplicate/source identity, parameters and preflight | Retain A03-01–08 and A06-01–09; real browser batch/cancel/retry checks |
| RD04 | Source semantics, evidence, batching and completed-run archives remain accurate | Retain A04-02–06 fixture/contract tests; live checks when API code changes |
| RD05 | HTTP pacing charges requests and distributed worker/cache safeguards stay intact | Retain A01-09/10 request-hook/Lua/worker mismatch tests; no fleet certification claim |
| RD06 | Software licenses, independent versions, core floors and installed artifacts remain coherent | Retain A02-01/02/03/05 and package/scaffold conformance gates |
| RD07 | Installation, current inventory and human workflow docs remain usable | Retain A05-01–06; regenerate changed catalogs and validate links |
| RD08 | Publication stays inactive; cache/resume proceeds only after its new contracts | Publication #142 deferred; persistence spec governs #143 |

The recorded baseline is 1,239 pytest tests, five release-tool tests and 48 opt-in
skips; 32 API live tests, 17 strict weaver gates, 20 wheel/sdist pairs and Firefox
batch journeys passed. These are historical evidence, not a requirement to keep the
exact same test count. Preserve assertion strength and explain deliberate behavior
changes. Remote CI has not been run for these unpushed commits.

New implementation must pass the applicable contract tests and build on this
baseline. Do not rerun huge local-data live tests or install system tools to certify
routine refactors. Use isolated environments and tiny fixtures.
