# Backend availability diagnostics — specification

Issue [#132](https://github.com/rafaelmdc/braidworks/issues/132). Reviewed 2026-10-14
on branch `feat/backend-availability-diagnostics`, starting from `d52b1a1`.
This is a focused audit and implementation specification; runtime changes are not yet made.

## Need and scope

A caller should distinguish an unknown capability/output from a supported operation
whose backend was omitted or excluded by policy. Diagnostics must name the affected
source, capability and backend without performing source calls or changing execution.

Scope: core declaration/registration/planning, direct shared dispatch and CLI handling,
NCBI's handwritten dispatch/manifests, and scaffold support for future adapters.
The broader error-system issue #133, readiness-aware routing, retries/progress,
cache/resume changes and automatic backend enabling are outside this change.

## Evidence and current behavior

The original descendant example no longer fails: a local-only NCBI manifest now
includes `ncbi.list_children`, and the planner selects its local backend. API-only
gene/genome operations still demonstrate the same information loss.

The ignored reproduction at `.audit-local/backend-diagnostics/reproduce.py` constructs
real `NCBITaxonWeaver` instances with inert backend stubs. It does not download data,
open live services or execute lookups. The planner/dispatch paths are real; this is
not a replay against the original ORDINA environment.

| Case | Observed behavior | Assessment |
|---|---|---|
| Local-only NCBI, taxid → descendant records | Plans `ncbi.list_children` on local | Original concrete example already fixed. |
| Local-only NCBI, gene ID → `gene.symbol` | `NoPathError: no capability produces 'gene.symbol'` | Misleading: the implementation supports the output on API. |
| Same instance, direct `ncbi.describe_gene` on API | `UnsupportedCapability: 'ncbi' has no capability 'ncbi.describe_gene'` | Misleading: configuration removed it from the active manifest. |
| Full NCBI declarations, `LOCAL_ONLY`, gene ID → symbol | `NoPlanError: policy local_only permits no route ...` | Correct class, insufficient source/backend context. |
| Truly unknown output | `NoPathError` | Preserve this distinction. |
| Truly unknown capability | `UnsupportedCapability` | Preserve this distinction. |
| Declared local backend without data | `BackendUnavailable: backend 'local' is not configured ...` | Existing runtime classification is useful; preserve fallback behavior. |

Relevant owners:

- [NCBI manifest construction](../../weavers/ncbi_weaver/src/ncbi_weaver/vocab.py)
  omits API-only operations when API is not wired.
- [NCBI concrete weaver](../../weavers/ncbi_weaver/src/ncbi_weaver/weaver.py)
  assigns that filtered manifest as the instance `MANIFEST`.
- [Registry](../../braidworks-core/src/braidworks/core/registry.py)
  stores only the instance manifest; the graph therefore cannot retain omitted capabilities.
- [Planner](../../braidworks-core/src/braidworks/core/planner.py)
  already distinguishes policy blocking from absence using an unrestricted active graph.
  That graph still lacks capabilities omitted by source construction.
- [Shared dispatch](../../braidworks-core/src/braidworks/core/dispatch.py),
  [NCBI dispatch](../../weavers/ncbi_weaver/src/ncbi_weaver/dispatch.py) and
  [direct CLI](../../braidworks-core/src/braidworks/core/cli.py)
  use active declarations to decide whether an operation exists.

## Behavior and requirements findings

| ID | Impact | Finding | Recommendation and confidence |
|---|---|---|---|
| BA-01 | High | Disabled capabilities look structurally absent in planning and direct execution. | Preserve an optional full declaration for diagnostics, separate from active routing. Reproduced with API-only NCBI operations; high confidence. |
| BA-02 | Medium | Policy-blocked planning reports only the target/policy, requiring the caller to reconstruct the unavailable edge. | Name blockers on a connecting declared route, including relevant backend choices. Current policy classification is already correct; high confidence in the diagnostic gap. |
| BA-03 | Medium | Python dispatch does not consistently check whether a selected backend supports the named capability before calling it. CLI has this check, but direct Python calls bypass it. | Add a declaration-based preflight shared by the dispatch boundaries; reject incompatible backend/capability pairs before source work. This is a validation fix, not just a message rewrite. |

## Design and refactoring findings

| ID | Finding | Concrete benefit and tradeoff |
|---|---|---|
| BA-D01 | One manifest currently answers both what an instance exposes and what the implementation supports. Filtering legitimately narrows execution but destroys diagnostic context. | Add a small optional declaration hook on `BaseWeaver`. Keep `MANIFEST` authoritative for current routing, exports and persistence. One existing `WeaverManifest` shape avoids inventing a second capability schema. Legacy adapters need no changes. |
| BA-D02 | CLI, shared dispatch and handwritten dispatch own similar missing-capability/backend explanations. | Centralize declaration-aware lookup/formatting in a small domain-neutral helper. Boundary callers retain their exception/exit behavior. Avoid a new error framework or a hierarchy of diagnostic strategies. |

The two-manifest distinction is a scoped interface addition, not a behavior-preserving
rename. BA-03 changes invalid-call behavior deliberately. Successful routing, fallback
and result semantics should remain unchanged. The catalogue is diagnostic metadata,
not a promise that a backend is configured or that upstream data are available.

## Proposed contract

1. Add `BaseWeaver.declared_manifest()` returning `MANIFEST` by default. Sources may
   override it with their full implementation declaration, without constructing backends,
   downloading, checking credentials or reading data artifacts.
2. NCBI returns its complete declaration with local/API support. New scaffolds produce
   the hook from spec backend names. Existing adapters without the hook override report
   only what their active manifest establishes; diagnostics must not infer hidden support.
3. Registry retains validated declared metadata beside active metadata. Source identity
   and active capabilities must agree with that declaration; active backend sets may
   narrow declared backend sets. Define and test the precise consistency rules before coding.
   Use existing manifest validation rather than allowing empty-backend capabilities.
4. The execution graph remains derived from active manifests. On a planning failure,
   a diagnostic-only projection can establish whether a connecting declared route is
   blocked by omitted backends or the requested policy. Honor excluded capabilities and
   existing graph restrictions, including non-routable conjunctions and self-loop behavior.
5. Use `NoPlanError` when declarations establish a route but configuration/policy
   prevents execution. Keep `NoPathError` for truly unknown or disconnected paths.
   Messages include target, relevant source/capability, declared/active backends and
   policy where applicable. Sort output deterministically. Do not suggest a specific
   builder argument that core cannot know.
6. For direct calls, known-but-inactive operations raise `BackendUnavailable` with
   supported backend context. Unknown operations remain `UnsupportedCapability`.
   A backend outside the capability's supported declaration fails before source calls.
   Declared but unconfigured backends continue to use existing runtime checks/fallback.
7. CLI/browser/query surfaces reuse this context without adding a new response schema
   or serializing live objects. Explicit-capability planning receives the same distinction.
   Do not print option values, credentials or client internals.

A sample diagnostic, illustrating content rather than exact wording:

```text
Cannot plan gene.ncbi.id -> gene.symbol:
  ncbi / ncbi.describe_gene supports backend api;
  api is not enabled in this instance. Enable the required backend and retry.
```

## Acceptance criteria

- API-only NCBI operations omitted by local-only construction receive configuration
  diagnostics in routed and direct calls; local descendant planning remains successful.
- Policy-only restrictions name source/capability/backend context.
- Unknown targets, disconnected inputs, absent sources, explicit exclusions and unknown
  capabilities retain honest distinctions. A declaration does not invent a reachable path.
- Alternate executable routes still win, even when another declared source is disabled.
  Successful plans and executor fallback order remain identical to existing behavior.
- Diagnostic lookup performs no source work; a failing direct preflight calls no backend.
- Legacy adapters with only `MANIFEST` remain supported. Catalogue consistency errors
  fail clearly without weakening registration or conformance checks.
- Direct CLI, Python and browser planning retain existing failure channels with better
  context. No implicit downloads, enabling, constructor prompts or readiness probes.
- Focused tests cover outcomes, not only wording. All required suites/lint stay green.

## Limitations and preserved boundaries

The catalogue diagnoses omitted declarations; it does not inspect actual provider
availability. A wired backend may still lack data, credentials or network access.
That remains a runtime availability/failure concern. No registration warning is needed:
selecting a local-only instance is legitimate and should not generate noise.

No NCBI identifiers or builder flags belong in core. Keep API batching, source identity,
review, per-input failures and persistence identity semantics unchanged. This audit
neither establishes #131's current retry behavior nor scopes #133's full error refactor.
