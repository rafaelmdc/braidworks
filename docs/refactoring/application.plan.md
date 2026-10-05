# Round 3 plan: application and interface boundaries

Spec: [application.spec.md](application.spec.md). Detailed design:
[application refactor](../audits/application-patterns.plan.md).
Cross-round order: [W04–08, W13](implementation.plan.md).
Status: planned; no work below is implemented yet. Tracking: #145, #146.

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

## A07b — Retry decisions

Agree a small explicit classifier: transient exceptions retry with existing bounds and
jitter; unsupported/configuration/programmer failures do not. Preserve failure result
values and source-specific HTTP policy. Coordinate larger exception-taxonomy work with
#133; do not rewrite it incidentally. Transport output remains adapter-owned.

Tests mock worker retries, attempts and nonretryable failures; preserve cardinality,
identity and pacing assertions. Do not broaden core transport dependencies. Record
any exception-category decisions before commit. AP07 completes when both tasks pass.

## A08 — Optional NCBI adapter assessment

Compare every custom dispatch capability to core runtime behavior and map compatible
records through a source-local adapter only if it reduces coupling. Keep taxonomy
candidate semantics and allowed custom runtime. Reject adaptation if it requires
source-specific core hooks or widened domain-neutral records.

Record capability equivalence table and implementation or rejection rationale. If
implemented, run NCBI direct/routed, resolver/lookup, parameter/group/cardinality and
conformance tests; changed API behavior also requires live E2E. A documented justified
rejection satisfies AP08; no change solely to eliminate a second dispatch class.

## Evidence, validation and exit

Track Planned / In progress / Verified per task with acceptance results and local hash.
Preserve public wrappers and readiness invariants. Run affected package tests first,
then workspace checks at integration points and W14 installed-artifact/browser checks.
Bump independent packages and floors only when required by their public changes.
No unrequested frameworks/dependencies, system installs, push, merge or publication.
