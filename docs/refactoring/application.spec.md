# Round 3 implementation spec: application boundaries

Matching plan: [application.plan.md](application.plan.md).
Status: AP01–AP06 verified locally; AP07 planned; AP08 conditional. Tracking:
[#145](https://github.com/rafaelmdc/braidworks/issues/145).
Evidence: [N01–N09](../audits/application-patterns.spec.md).
Detailed module/method design: [application plan](../audits/application-patterns.plan.md).

## AP01 — Normalized request/options boundary

Trace: N02. Core owns QueryRequest/QueryOptions values with JSON round trips; transport
models adapt into them. Already parsed inputs preserve ordering, duplicate/source
identity and caller state. Normalize expansion syntax/defaults once. Validate all
settings/parameter scopes before source I/O. No FastAPI/Pydantic imports in core.
Keep existing public signatures as wrappers. Routed/traversed requests are the first
scope; direct capability calls remain direct until equivalent semantics are proved.

Acceptance: CLI/Python/browser normalize equivalent experiments into equivalent
values; invalid mode, threshold, budget, scope or input fails before calls. JSON
round trips preserve options. Existing fetch unique-ID convenience semantics remain.

## AP02 — Shared prepare/execute application service

Trace: N01. prepare_query performs whole-request grouping/planning/preflight and returns
PreparedQuery. execute_query is async, uses existing executor/traversal and shared
budget, and aggregates terminal data/references deterministically. Sync facades alone
own asyncio.run. Interfaces retain output and exit/HTTP conventions. Core does not
import weaverkit. The service does not own cache schemas or checkpoint transactions.

Acceptance: heterogeneous routes all validate before calls; mixed outcomes, duplicates,
parameters, backend policy, review/confidence, traversal, fan-out bounds and reroutes
retain readiness behavior across CLI/API/browser. Existing executor/runner APIs remain.

## AP03 — Prepared-query presentation and code generation

Trace: N03. Code and graph renderers consume PreparedQuery plans/effective options;
they do not replan or execute sources. Share shell-token construction with safe quoting.
Generated Python invokes the core query service rather than a browser helper. Preserve
existing serve/view wrappers and artifact response fields. Biological labels stay in
weaverkit; terminal records reuse outcomes.py.

Acceptance: actual generated CLI and Python execute equivalent deterministic fixtures,
including tables/traversal/review/parameters. Renderer tests verify zero source calls
and no replanning. Installed core execution does not require weaverkit serve extras.

## AP04 — One streaming transport lifecycle

Trace: N04, N08. GET/POST decoding adapts to one execution stream helper. It owns,
cancels and joins the execution task; reliable completion/error events cannot be
lost when progress is coalesced or consumers are slow. Expected failures are translated
at transport boundaries; unexpected failures retain diagnostics. Preserve existing SSE
fields and endpoint compatibility. No event bus or broker.

Acceptance: both endpoints, malformed input, cancellation/disconnect, slow consumer,
terminal ordering and retry pass. Browser journeys remain necessary alongside unit tests.

## AP05 — One browser experiment encoder

Trace: N05. Extend existing experimentState and extract pure normalization/request
encoding. Preview/run/code/recipes consume the same snapshot. Graph auto expansion
resolves before request creation. Experiment settings are separate from animations
and results. Keep self-contained static/offline views, accessible controls and optional
serve install. No required frontend framework/build chain.

Acceptance: typed/graph request parity, recipe roundtrip, real batch upload, cancellation,
code generation, exports and keyboard/modal focus journeys. Preserve old saved recipes.

## AP06 — Scaffold functional core and publication shell

Trace: N06. generate_files returns relative-path contents without filesystem mutations.
Render original template tokens once, never reinterpreting inserted values; escape
values for their target language. Validate bindings, generated Python syntax and
conflicts before writes. Existing scaffold wrapper preserves explicit force and optional
format semantics. Include external templates in artifacts if templates move out of Python.
Never regenerate handwritten NCBI vocab.

Acceptance: observed token-substitution regression, quotes/newlines, missing bindings,
unchanged destination on prevalidation failure, generated variants importing, strict
conformance/golden gates and installed-wheel scaffolding. No abstract builder hierarchy.

## AP07 — Discovery and retry policy seams

Trace: N07, N08. Shared discovery offers structured failures with explicit strict/tolerant
policy, pre-import filtering and compatible wrappers. Arq retains worker-local registry
ownership. Worker retry decisions distinguish transient exceptions from structural or
programmer failures; normal WeaveResult values retain existing fallback behavior.
Coordinate larger error-system changes with #133 rather than quietly broadening scope.

Acceptance: excluded plugins never import; strict errors and partial views retain
behavior; unsupported/configuration/programmer errors do not retry; explicitly transient
failures follow bounded jittered retry. No global core singleton or generic exception
framework. Source-specific HTTP classifications remain source-local.

## AP08 — Conditional NCBI adaptation and preservation of good boundaries

Trace: N09. Assess compatible custom-dispatch paths against core runtime. Implement
only when an adapter reduces duplication without widening domain-neutral core records
or weakening taxonomy semantics. A documented rejection is an acceptable outcome.
Keep Braider, BackendPolicy, WeaveStepRunner, shared mappers and thin weaver contract.
Do not add speculative route algorithms or subclass-per-policy structures.

Acceptance: capability-by-capability equivalence evidence; existing NCBI contracts and
live API gate if behavior changes, or a recorded reason to retain custom dispatch.
