# Application design-pattern audit

Tracking: [#145](https://github.com/rafaelmdc/braidworks/issues/145).
Date: 2026-10-05. Scope: query orchestration, human interfaces, code generation,
streaming, browser state, scaffolding, discovery, worker error policy and weaver
runtime composition. Cache, databases, checkpoint storage and resume state are
excluded; their separate [persistence design](persistence-refactor-design.md) remains
unchanged. Focused main-agent source audit, not a new multi-agent review.

These findings concern responsibility and coupling, not file length or an arbitrary
pattern quota. Existing test coverage informs acceptance; implementation is unchanged.
Only N06's substitution behavior was independently reproduced in this audit.

## Findings and recommended patterns

| ID | Priority | Area | Useful change | Pattern |
|---|---|---|---|---|
| N01 | High | CLI/API/browser orchestration | One shared prepare/execute query service | Application service / facade |
| N02 | High | Input settings and validation | Normalized request/options values with interface adapters | Request object / adapter |
| N03 | High | Generated code and presentation | Render an already prepared query rather than plan it again | Presentation adapter / functional core |
| N04 | Medium | GET/POST streaming | One task/stream lifetime helper over shared execution | Observer callback and resource scope |
| N05 | Medium | Browser experiment state | Extend the existing experiment snapshot and use it for every action | State value plus pure transformation |
| N06 | Medium | Scaffold rendering and publication | Pure generation plan followed by validated file writes | Functional core / imperative shell |
| N07 | Low | Plugin discovery | Shared discovery mechanics with explicit strict/tolerant policy | Policy parameter / adapter |
| N08 | Medium | Worker retries and interface failures | Explicit error translation/retry decisions at their boundary | Policy function, no exception framework |
| N09 | Conditional | NCBI custom dispatch | Adapt record mapping where the shared runtime actually fits | Strategy / adapter, preserve justified custom runtime |

## N01 — One preparation/execution service

Evidence: `core/cli.py:_cmd_weave` groups inputs, plans every group, gathers capabilities,
validates parameters, constructs a shared expansion budget, executes and aggregates
results. `weaverkit/serve.py:execute_batch_response` repeats these responsibilities.
`run_response`, `run_traversed_response` and legacy GET streaming have additional paths.
`core/fetch.py:async_fetch` separately plans and executes, then translates to FetchResult.
Shared low-level helpers already exist but application orchestration remains duplicated.

The consequence is change amplification: a policy or heterogeneous-input improvement
needs changes in several places. This audit did not establish a new runtime parity bug.
Create a domain-neutral query preparation/execution service in core. Interfaces own
parsing, display and exit/HTTP conventions; they call the same service. Preserve
existing direct `BaseWeaver` and executor APIs for callers who need that control.
No service locator, operation-class hierarchy or framework dependency in core.

## N02 — Normalized request and options

Evidence: CLI argparse options, FastAPI's closure-local request models, Python keyword
arguments and browser dictionaries pass overlapping settings independently. Expansion
uses `none/top:N/all` in CLI and `top/top_k/all` in browser; `_expand_policy` in serve
coerces/clamps settings while code-generation functions validate them separately.
Parameter adapters already share `core/parameters.py`; extend that established seam.

Use a small immutable `QueryOptions` value and a normalized `QueryRequest` after input
parsing. Preserve per-interface syntax and legacy defaults explicitly; normalize into
one representation before preflight. Validate requested mode, confidence, budget and
parameter scopes before I/O. Request values must round-trip through JSON.
Do not introduce the Command pattern merely because functions execute queries: there
is no undo/history requirement for these operations.

## N03 — Prepared queries as the presentation boundary

Evidence: `serve.py:code_response` and `batch_code_response` re-plan and validate settings,
then duplicate shell token construction. Batch-generated Python imports
`weaverkit.serve.execute_batch_response`, tying generated execution to a browser module,
even though that helper does not require FastAPI. View `build_path` also plans to render
a path; execution sometimes asks it to plan again after completing a run.

Represent preparation explicitly so rendering can consume plans/effective options
without repeating planning. Keep code-generation and graph presentation in weaverkit;
move execution out of serve. Generated Python should call a stable core service.
Preserve the existing FetchResult facade's unique-ID convenience behavior rather than
silently making it a duplicate-preserving batch API. Do not require all output formats
to share identical envelope shapes: they need equivalent data and settings.

## N04 — Shared stream lifetime

Evidence: GET and POST `/api/run/stream` separately create queues/tasks, translate events,
wait for completion and clean up on cancellation. POST uses the new batch helper; GET
still contains its own plan/validate/execute path. Both endpoints intentionally remain
supported. This audit has not proven a new disconnect leak.

Decode GET/POST requests differently, then call one async iterator wrapping the shared
query service. Make task ownership/cancel/join behavior explicit. Keep terminal results
and errors reliable; coalesce optional progress if a bounded queue is full rather than
losing completion or blocking a synchronous callback. No pub/sub bus or broker.
Progress and terminal execution outcomes remain separate concepts.

## N05 — Complete the existing browser state seam

Evidence: `_serve_ui.py` already contains `experimentState()` for recipes, but `runBraid`,
`runBuild` and `showCode` also build request bodies directly from DOM controls/global
`build` and `lastPlan` state. Typed and graph modes differ in how automatic expansion
and values are selected. The last fixes improved parity but leave multiple encoders.

Use the existing experiment snapshot as the canonical input to a pure normalizer.
Run, preview, recipe save and code generation all consume it. Explicitly resolve graph
`auto` expansion before building the shared request. DOM handlers read/write controls;
normalization and request encoding are testable plain JavaScript functions. Keep local
animation/result state outside experiment settings. No Redux, React migration, global
immutable-store framework or event-sourcing machinery. Preserve offline static views.

## N06 — Scaffold render plan before writes

Evidence: `scaffold.py:scaffold` currently decides artifact selection/tokens, renders,
writes files and invokes a formatter in one function. `_render` repeatedly replaces
strings. Reproduction:

```python
_render('title={{TITLE}}', {'TITLE': 'literal {{VERSION}}', 'VERSION': '0.1.0'})
# Actual: 'title=literal 0.1.0'; literal inserted data was interpreted as another token.
```

This confirms substitution behavior, not a demonstrated exploit or broken full package.
Separate `generate_files(spec, raw_spec)` from filesystem publication. Return a
path-to-content plan using relative paths. Render template placeholders once; escape
Python literals, TOML strings and HTML/Markdown according to their target context.
Reject missing template bindings; do not interpret tokens introduced by user values.
Validate generated Python syntax and destination conflicts before writing. Preserve
`--force` semantics and the NCBI handwritten-vocab exception. Best-effort formatting
remains optional and should not conceal failed generation. A dictionary/table selects
known backend templates; no abstract builder factory per backend variant.

## N07 — Discovery policy without duplicate mechanics

Evidence: `core/discovery.py` filters entry-point names before loading and builds a
strict registry. `weaverkit/view.py:discover_registry` separately enumerates/loads
entry points and records per-source failures so the view can remain partial. Arq
already reuses core discovery and retains a worker-local registry. Strict CLI and
tolerant visualizer behavior are legitimate differences.

Expose a shared discovery result containing registry and structured failures, with
an explicit strict/tolerant policy. Preserve strict wrapper behavior and pre-import
filtering. Rendering owns friendly failure text. Worker ownership remains local to
arq; do not move its cached registry into a global core singleton. A policy argument
and functions suffice; no discovery-strategy hierarchy is necessary.

## N08 — Retry and transport translation

Evidence: `arq/tasks.py:weave_step` rethrows BackendUnavailable/BackendConfigurationError
but retries any other Exception up to MAX_TRIES. This may include programming or
unsupported-capability errors; this audit did not independently execute those paths.
Core executor and browser/CLI independently translate domain failures into their
appropriate output conventions. Existing failures-as-values semantics are intentional.

First document a decision table: structural configuration/unsupported requests fail
without retries; explicitly transient failures may retry; NO_MATCH/ERROR result values
retain core fallback policy. A small pure classifier can support worker tests. Keep
HTTP retry/error handling source-specific where it depends on the provider. Transport
adapters choose CLI exits, JSON or SSE messages; core must not raise SystemExit or
construct JSONResponse. Avoid a broad exception-class rewrite while doing this refactor;
coordinate any larger changes with existing error-system issue #133.

## N09 — Conditional NCBI consolidation

Evidence: core's BackendDispatchWeaver and NCBI's source-local dispatch both manage
backend selection, fingerprints, single/batch bridging and mapping. NCBI's taxon-match
records and lookup capabilities deliberately use distinct paths; ordinary generated
weavers already share core record mappers. The custom runtime is a supported escape hatch.

Only extract a small adapter/shared helper when its behavior is proven equivalent.
A source-local adapter could normalize compatible NCBI lookup records into the core
runtime while retaining taxonomy-specific matching. Do not force all NCBI capabilities
through one generic record if that obscures candidate semantics. A failed fit is a
valid rejection of this refactor, not a reason to enlarge the core contract.

## Existing patterns that should stay

- Braider already separates route computation from executor I/O and serializes Braid.
  Do not add pluggable routing algorithms until there is a second real algorithm.
- `BackendPolicy` and capability declarations express policy as data; do not replace
  each enum branch with a subclass.
- `BackendDispatchWeaver`, `WeaveStepRunner`, record mappers and WeaverFactory provide
  useful Strategy/Adapter/factory seams. Keep the thin-contract escape hatch.
- `outcomes.py`, `parameters.py`, `inputs.py` and JSON boundary values are functional
  helpers worth reusing. No generic pipeline framework is required.
- Keep source-specific request/response normalization close to each backend. Similar
  HTTP syntax alone does not justify a universal biological-provider client.

## Audit confidence and scope limits

N01–N05 and N07–N09 are source-confirmed maintenance opportunities, not a claim that
existing behavior fails. N06's small substitution probe ran against current code.
No benchmarks, new full runtime regressions or refactor implementations were run.
Previous readiness validation remains a baseline, not certification of the proposed
architecture. See the [concrete refactor plan](application-patterns.plan.md).
