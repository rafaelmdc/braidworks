# Round 3 plan: application and interface boundaries

Spec: [application.spec.md](application.spec.md). Detailed design:
[application refactor](../audits/application-patterns.plan.md).
Cross-round order: [W04–08, W13](implementation.plan.md).
Status: A01–A07 verified locally; A08 assessed, adapter rejected with evidence. Tracking: #145, #146.

| Task | Requirement | Deliverable | Dependency |
|---|---|---|---|
| A01 | AP01 | QueryRequest/Options and interface normalization | W00 |
| A02 | AP02 | Shared prepare/execute service and wrappers | A01 |
| A03 | AP03 | Prepared-query graph/code presentation | A02 |
| A04 | AP04 | Shared streaming adapter | A02–03 |
| A05 | AP05 | Canonical browser experiment encoder | A03–04 |
| A06 | AP06 | Pure scaffold generation/validation/writes | W00; align current runtime floor |
| A07a | AP07 | Structured discovery with policy | W00 |
| A07b | AP07 | Worker retry classification | W00; coordinate #133 |
| A08 | AP08 | Conditional NCBI adaptation assessment | PF03, A02, A07 |

## A01 — Shared request values and adapters

Inventory CLI argparse, Python kwargs and FastAPI/browser settings/defaults. Define
small frozen QueryOptions/QueryRequest values with JSON round trips. Normalize current
expansion syntaxes and scoped/bare parameters through existing helpers. Preserve input
order/source_row and caller-owned state. Keep Pydantic optional and out of core.

Tests exercise equivalent experiments and invalid input without source calls. Preserve
fetch's unique-ID convenience and direct-capability call semantics explicitly. Do not
force direct CLI `run` through the routing planner. Commit values/normalizers before
replacing orchestration; keep current public signatures as wrappers.

## A02 — Prepare/execute application service

Implement core prepare_query returning PreparedQuery after validating every input group;
async execute_query composes existing executor/traversal, shared budget and deterministic
aggregation. Reuse original algorithms; do not duplicate execution or checkpoint logic.
Move orchestration from CLI and serve helpers; adapt async_fetch as a thin convenience
facade. Sync wrappers own asyncio.run, presenters own exit/response conventions.

Tests: mixed terminal rows, duplicates, heterogeneous preflight, effective parameters,
backend policy, review/confidence, fan-out/traversal and references. Check core never
imports weaverkit/server dependencies. Preserve old wrappers while migrating callers.
Commit the service and meaningful adapter parity regressions at a coherent boundary.
Coordinate stable option/input definitions with PF05; service does not own persistence.

## A03 — Render prepared plans and generated code

Extract weaverkit code generation over PreparedQuery. Share shell-token construction
and quote input text safely. Generated Python calls core's public service. Add a
planned-Braid view renderer while retaining plan-and-render convenience wrappers.
Use existing shared terminal record data, with human labels in toolkit presenters.

Execute generated CLI/Python on deterministic fixture registries; verify settings,
batch rows, traversal/review/expansion and output equivalence. Renderer tests assert no
source calls and no replanning. Preserve artifact keys. Rehearse installed-wheel code
without FastAPI and document the required core version. Commit renderers/wrappers with
version/floor updates rather than leaving an intermediate broken generated script.

## A04 — Stream transport lifecycle

Extract a toolkit async iterator owning task creation, queue/event translation and
cancel/join cleanup. GET/POST handlers only decode/adapt and delegate. Preserve SSE
fields, terminal events and endpoint behavior. Bound/coalesce optional progress safely;
never drop completion/errors. Expected domain failures translate at the boundary;
unexpected failures retain logs/context. No pub/sub bus.

Tests cover both endpoints, bad input, disconnect/cancel, slow consumers, terminal
ordering and retry. Real Firefox journeys verify browser fetch/cancellation. Keep
post-application checkpoint hook distinct from presentation progress. Commit streaming
independently from browser state restructuring where feasible.

## A05 — Browser experiment normalization

Extend experimentState, add pure normalizeExperiment/toQueryRequest functions and
route preview/run/code/recipes through them. Normalize graph auto expansion explicitly.
Keep animation/results state separate and old recipe loading compatible. If JS source
is split, embed/concatenate into the existing self-contained HTML; do not require a new
build system/framework. Preserve accessible controls and offline views.

Tests compare typed/graph request bodies for the same experiment. Rehearse upload,
recipe, generated code, exports, cancellation/retry, keyboard navigation and modal focus
in Firefox. Commit state encoder plus callers; do not merely move the existing globals
into a differently named file and call the refactor complete.

## A06 — Scaffold functional core and publication shell

Detailed [A06 specification](scaffold.spec.md) and [implementation plan](scaffold.plan.md)
expand this work package into SC01–SC05 and S01–S04. Status: verified locally.

Implementation commit: `ce33f19` (local, unpushed).

Acceptance: toolkit 0.6.1; workspace 1,402 passed/48 skipped, lint/format clean;
wheel/sdist and six installed scaffold variants at exact core 0.20.0 passed.
See the detailed plan for preflight, metadata and strict TODO-gate evidence.

Split scaffold into pure artifact plan, single-pass target-aware rendering, validation
and filesystem publication. Preserve scaffold wrapper/force/format behavior. Reject
missing bindings and invalid Python before writes. Inserted placeholder-like data is
literal; regression the reproduced substitution behavior. No abstract factory hierarchy.

Tests cover generated lookup/resolver, keyed/keyless API and bulk variants; quoted and
multiline values; missing tokens; conflict/prevalidation failure without overwrite;
imports, conformance/goldens and installed-wheel generation. If moving templates to
resources, verify wheel/sdist inclusion. NCBI vocab remains handwritten. Commit the
pure plan/renderer first if compatibility wrappers keep generation functional, then
publication validation; do not imply a multi-file transaction without implementing it.

## A07a — Discovery mechanics and policy

Add structured registry/failure discovery with explicit strict/tolerant policy and
filter-before-import. Keep current strict core and tolerant view wrappers. Reuse
mechanics in toolkit; arq owns worker-local registry lifetime. No global core singleton.

Tests fake entry points to prove excluded imports never occur, strict failures raise,
partial views report failures and valid plugins register. Preserve user-facing error
context. Commit independently from query/stream layers.

### A07a implementation evidence — 2026-10-08

Implementation commit: `40dbb94` on `refactor/persistence-foundations` (local, unpushed).

Verified locally. Core exposes `DiscoveryPolicy`, `DiscoveryFailure`, `DiscoveryReport`
and `discover_registry`; strict `build_registry_from_entry_points` and builder iteration
remain compatible. One shared metadata filter precedes plugin imports. Reports contain
entry-point name/value, load/build/register stage, exception type and message; failures
round-trip JSON without retaining tracebacks. The report holds live registry instances
and is deliberately not a serialized registry format.

Strict discovery re-raises the original exception with an entry-point/stage note.
Tolerant mode continues after per-plugin failures; metadata enumeration errors and
process-control exceptions propagate. Toolkit's existing Discovery wrapper retains its
registry/problems shape and friendly text. Arq's cached registry stays worker-local;
its implementation and version are unchanged. No global core registry or retry changes.

- Core **0.21.0** for additive public discovery APIs; toolkit **0.6.2**, floor
  **core>=0.21.0**, lock synced in the isolated environment. Weaver versions unchanged.
- Targeted discovery/view/CLI/worker suites passed; full workspace **1,415 passed,
  48 skipped** plus release-tool unittests. Core 523, toolkit 258, arq 52 passed.
- Lint, changed-file formatting and diff whitespace checks passed.
- All **20 packages** built wheel/sdist; Twine, metadata/resource checks and clean
  installed CLI/fixture/server smoke passed. Artifact floor guard recognizes new APIs.
- Separate clean installed core/toolkit minimum-floor check with real PDBe and an
  intentionally broken plugin passed strict exception context, pre-import exclusion,
  partial discovery and matching friendly view diagnostics. Temporary environments removed.

Evidence: `.audit-local/a07a-tests.log`, `a07a-lint.log`, `a07a-build.log`,
`a07a-twine.log`, `a07a-artifact-check.log`, `a07a-installed.log`. No backend changes
or live API calls. A07a was completed separately; see A07b evidence below for AP07/W08 completion.

## A07b — Retry decisions

Agree a small explicit classifier: transient exceptions retry with existing bounds and
jitter; unsupported/configuration/programmer failures do not. Preserve failure result
values and source-specific HTTP policy. Coordinate larger exception-taxonomy work with
#133; do not rewrite it incidentally. Transport output remains adapter-owned.

Tests mock worker retries, attempts and nonretryable failures; preserve cardinality,
identity and pacing assertions. Do not broaden core transport dependencies. Record
any exception-category decisions before commit. AP07 completes when both tasks pass.

### A07b decision table — verified locally, 2026-10-08

Worker retry is an allowlist of concrete Python connection/timeout, Redis
connection/timeout and optional HTTPX NetworkError/TimeoutException types. Domain
exceptions and Redis AuthenticationError/AuthorizationError take precedence and do not
retry. Unsupported/configuration/contract/programming/unknown errors propagate, as do
HTTP status exceptions; source HTTP policy stays in backends. NO_MATCH/ERROR values,
request pacing, identity checks, cancellation and transport translation are unchanged.
The existing three-attempt bound and delay range `[0.5, 1.5) * 2**(attempt-1)` stay intact.
HTTPX is optional at runtime, explicit in arq test extras; no new required/core dependency.
Arq patch version becomes 0.2.1; its actual core>=0.13.0 floor remains unchanged.

The old general retry test used RuntimeError as a transient stand-in. It now uses an
explicit TimeoutError, and a new regression proves RuntimeError propagates without retry.
This changes the tested retry contract deliberately per AP07; conformance/batch/identity/
pacing checks are preserved. Broader error taxonomy (#133) is unchanged.

### A07b acceptance evidence

Implementation commit: `e8c2852` on `refactor/persistence-foundations` (local, unpushed).

`retry.should_retry` is a pure worker-local allowlist; `weave_step` uses it before
raising arq Retry. Final-attempt and nonretryable failures preserve the original
exception; retry signals retain the exception as their cause. The existing batch
execution scope, jitter function, fallback/result translation and request budgets stay
intact. Arq 0.2.1 and lock updated; core, toolkit and weaver versions unchanged.

- Full workspace **1,481 passed, 48 skipped** plus release-tool unittests; arq
  **118 passed, 2 skipped**, including 66 new retry cases. Pacing, cardinality,
  identity and fallback regressions remain green.
- Concrete transient/nonretryable exceptions tested at attempts 1, 2 and 3; fixed
  random input proves the preserved backoff delay. Empty HTTPX timeout text,
  misleading programmer-error text, Redis auth inheritance, cancellation and normal
  NO_MATCH/ERROR results are covered.
- Lint, changed-file Ruff format and whitespace checks passed.
- All **20 packages** built wheel/sdist; Twine, metadata/resources and clean installed
  fixture/CLI/server smoke passed. Separate clean installation with exact historical
  **core 0.13.0** and **no HTTPX** passed batch execution, bounded retry and immediate
  unsupported-capability failure. Temporary environments removed.
- Evidence: `.audit-local/a07b-tests.log`, `a07b-lint.log`, `a07b-build.log`,
  `a07b-twine.log`, `a07b-artifact-check.log`, `a07b-installed.log`.

AP07/W08 now verified locally (A07a plus A07b). No core exception-taxonomy rewrite
or source backend changes; #133 stays separate. Opt-in real Redis integration tests
remain skipped; worker policy was exercised with deterministic doubles, not a live
broker. A08 assessment and final programme acceptance remain.

## A08 — Optional NCBI adapter assessment

Compare every custom dispatch capability to core runtime behavior and map compatible
records through a source-local adapter only if it reduces coupling. Keep taxonomy
candidate semantics and allowed custom runtime. Reject adaptation if it requires
source-specific core hooks or widened domain-neutral records.

Record capability equivalence table and implementation or rejection rationale. If
implemented, run NCBI direct/routed, resolver/lookup, parameter/group/cardinality and
conformance tests; changed API behavior also requires live E2E. A documented justified
rejection satisfies AP08; no change solely to eliminate a second dispatch class.

### A08 assessment evidence — 2026-10-08

Completed conditional assessment: [capability comparison and decision](ncbi-dispatch-assessment.md).
Keep the source-local runtime. Six capabilities already share core lookup mapping;
generic taxonomy conversion demonstrably changes ambiguous candidate projection and
loses warnings. A custom mixed-mapper adapter is possible but retains the same source
branches plus a forwarding layer, without a second reusable mixed-source requirement.
No core hooks/records were widened; no backend/vocab/version changes. NCBI 126 passed,
11 skipped, plus local mapper/parameter counterexample probe. AP08/W13 satisfied by
specified documented rejection; final W14 acceptance remains.

## Evidence, validation and exit

Track Planned / In progress / Verified per task with acceptance results and local hash.
Preserve public wrappers and readiness invariants. Run affected package tests first,
then workspace checks at integration points and W14 installed-artifact/browser checks.
Bump independent packages and floors only when required by their public changes.
No unrequested frameworks/dependencies, system installs, push, merge or publication.

## A01–A02 implementation evidence — 2026-10-05

core.query supplies QueryOptions, QueryRequest and PreparedQuery JSON values, expansion
normalization, prepare_query and async execute_query. Preparation copies caller state,
preflights all heterogeneous groups and resolves effective parameters through existing
validators. Execution composes existing executor/traversal with one expansion budget,
deterministic result/reference aggregation and existing progress events.
CLI routed/traversed weave, async_fetch and browser single/batch/traversal helpers use
this service. Direct CLI run retains its semantics. Fetch still collapses duplicate IDs;
query rows preserve duplicates/source_row. Toolkit retains envelopes, human diagnostics,
archives and unset-parameter displays. Core imports no server/toolkit dependencies.
Traversal accepts an injected executor and propagates its backend policy to reroutes.

Core 425 tests and toolkit 221 tests pass; full workspace suite passes. New tests cover
JSON request/prepared roundtrips, duplicate heterogeneity, caller-state isolation,
all-group preflight and expansion/confidence validation. Existing parameter, review,
fan-out, archive, CLI/fetch/browser contracts retained. Core 0.14.0, toolkit 0.5.1/floor
0.14.0. Render/code extraction, stream lifecycle and browser normalization remain A03–05.
Local commit: see `refactor(query): share preparation and execution across interfaces`.

## A03 implementation evidence — 2026-10-05

weaverkit.codegen renders shell/Python artifacts from PreparedQuery. Single/batch
wrappers share request preparation and effective settings. Python calls public core
prepare_query/execute_query, embedding normalized ordered inputs; no weaverkit.serve
or FastAPI import. Generated batch output now consistently uses ExecutionResult JSON,
matching single Python artifacts; the browser keeps its presentation envelope. This
intentional output boundary is documented in weaverkit/README.md. Artifact keys remain.
render_path projects an existing Braid; build_path remains the planning convenience.
Preview artifacts and completed single/batch result graphs reuse prepared routes.

224 toolkit tests pass, including actual generated CLI/Python fixture execution, source
rows, parameters, traversal/expansion, review settings and safe literal shell quoting.
New checks assert presentation never plans or executes and route preview/run plan once.
Ordinary generated-source assertions were deliberately updated to the new public service;
the executable batch regression now asserts core resolved rows/source order instead of
the old server envelope. No conformance/contract assertion was weakened.
Current core/toolkit wheels installed into a fresh repo-local venv without FastAPI;
generated Python ran and preserved two duplicate-label rows. Full workspace 1338
passed/48 skipped, make lint passes. Toolkit 0.5.2 retains core floor 0.14.0 (the
first shared service release). All minimum-floor artifact checks remain W14.
Local commit: see `refactor(presentation): render prepared queries and core Python examples`.

## A04 implementation evidence — 2026-10-05

streaming.query_events owns one query task and bounded progress queue (32 by default).
Oldest optional progress coalesces when full; completion/errors are emitted outside
the queue and never dropped. Iterator close/cancellation cancels and joins owned
execution. sse_events closes its underlying iterator explicitly. Domain failures retain
the existing error event; unexpected failures log their traceback and emit an actionable
terminal error. GET/POST handlers now decode/adapt and call execute_batch_response through
this common adapter, eliminating the GET-specific planner/executor/parameter path.
The post-application checkpoint hook remains separate; streaming stores no run state.

234 toolkit tests pass, including ten new lifecycle/slow-consumer/error contracts and
existing GET/POST expansion/parameter/review/batch parity tests. Real headless Firefox
passes pasted duplicate rows, recipe roundtrip, heterogeneous CSV upload, cancellation
with server task joined, and successful retry. No new browser/framework dependencies.
make lint passes; toolkit 0.5.3/core floor remains 0.14.0. Cancellation cannot terminate
already-running synchronous worker-thread work.
Local commit: see `refactor(streaming): share bounded SSE task lifecycle across endpoints`.

## A05 implementation evidence — 2026-10-05

Browser normalizeExperiment and toQueryRequest/toPlanRequest are pure functions.
experimentState only reads controls into the normalized recipe value. Typed/graph runs,
code generation and previews share encoders; new recipes save/load the same value, while
legacy loading remains supported. Graph auto resolves to all for traversals/top otherwise.
Repeated traversal tokens are preserved. Parameters/batch/values are copied; invalid
numeric settings fail visibly. Typed run/code/save use the displayed prepared type set
rather than silently combining edited selector types with earlier run controls.

Real Firefox checks pass for typed/graph encoder equality, automatic expansion, repeated
traversals, input immutability, numeric validation and recipe version compatibility.
Pasted duplicate rows, heterogeneous CSV upload, recipe reload, cancel/join and retry
journeys pass again. Existing toolkit suites pass; make lint passes. Toolkit 0.5.4;
no new JS tooling/framework/assets. Full accessibility/export/generated-code integration
rehearsal remains W14 with the P07 controls.
Local commit: see `refactor(browser): normalize experiments through shared request encoders`.
