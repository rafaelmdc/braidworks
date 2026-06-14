# Braidworks Implementation Plan

> **Status: historical (MVP shipped).** This is the original build-order plan for the
> core MVP — kept for the rationale and definition-of-done discipline it records. The
> MVP (registry, braider, executor, cache, the first weavers) is built and well past
> this scope; for what exists now and what's next see the [README](../README.md),
> [architecture.md](architecture.md), and [weaver-roadmap.md](weaver-roadmap.md).

This document defines the concrete implementation order for Braidworks. Each phase has a clear deliverable, a definition of done, and a note on what it explicitly does not include.

The goal is a working MVP: organism name → multiple NCBI strand types, resolved in batch, with caching, through a proper registry and braider. Everything beyond that is deferred.

---

## Revision (2026-06-04) — multi-backend core changes

Bringing the API backend into scope (TaxonWeaver ships `local` + `api`) surfaced two core contract changes that supersede the original Phase 1 spec below. They are generic — every future multi-backend weaver depends on them — and must be kept domain-neutral (no taxonomy/resolution assumptions in core):

1. **`BaseWeaver.dataset_version(self)` → `backend_fingerprint(self, backend: str) -> str`.** Per-backend, renamed for generality (a live API has no "dataset"). The executor evaluates it with `invocation.primary_backend` for the pre-check key and `result.backend_used` for the post-cache key, so a result is cached under the fingerprint of the backend that produced it.

2. **`StrandCacheKey` gains `weaver_id` + `weaver_version`; `dataset_version` → `backend_fingerprint`.** New shape: `(weaver_id, weaver_version, capability_id, backend, backend_fingerprint, input_fingerprint)`. The `WeaveResult.capability_version` field is **renamed to `weaver_version`** to match the key it feeds (executor reads `result.weaver_version` for the post-cache key). `compute_cache_key`, `CacheFingerprintTests`, and existing tests update accordingly. **`requested_outputs` and `computed_groups` stay OUT of the key** — they are handled by the existing superset validity check (`computed_groups` on the stored entry; `get(key, requested_groups)` does the `⊇` match). Putting them in the key would shard buckets and break superset reuse.

3. **New generic concept `BackendStrategy`** in core: identity only — `name`, `is_configured() -> bool`, `fingerprint() -> str`. No `resolve()` / no batch shape; core never calls a backend directly. The dispatch+mapper mixin and any per-domain intermediate (`TaxonMatch`) live in the weaver package, promoted to a shared `weaverkit` only when a second weaver (UniProt) proves the abstraction.

Phase 1 references to `dataset_version` / the old key shape below should be read through this revision.

---

## Phase 1 — `braidworks-core`: Types Only

**What:** Create the `braidworks-core` package containing all core dataclasses, enums, protocols, and exceptions. No graph, no planning, no execution, no weavers.

**Deliverables:**

- `strand.py` — `Strand`, `StrandSet`, `MergePolicy`
- `capability.py` — `OutputGroup`, `Capability`, `WeaverManifest`
- `result.py` — `WeaveResult`, `WeaveStatus`, `CandidateResult`
- `weaver.py` — `BaseWeaver` ABC with `execute`, `execute_batch`, `backend_fingerprint(backend)`, `_reorder_by_key` (see revision above; originally `dataset_version()`)
- `braid.py` — `CapabilityInvocation`, `Braid`, `BackendPolicy`, `FallbackCondition`
- `cache.py` — `StrandCacheKey`, `compute_cache_key`, `StrandCache` Protocol, `InMemoryStrandCache`
- `exceptions.py` — `BackendConfigurationError`, `BackendUnavailable`, `NoPathError`, `NoPlanError`, `UnsupportedCapability`, `ReviewRequired`, `MissingInputError`, `InvalidManifestError`

**Key structural points:**

**`OutputGroup`** has two fields: `id` and `outputs`. No `marginal_cost` (the MVP braider uses a single `Capability.cost` for Dijkstra; per-group costs have nowhere to feed in), no `depends_on` (internal weaver execution ordering is the weaver's responsibility). The weaver reports everything it computed in `WeaveResult.computed_groups`; that is the only mechanism the executor and cache use.

**`StrandCacheKey`** has no group information and no schema version (revised — see the multi-backend revision above):
```
StrandCacheKey
  weaver_id, weaver_version, capability_id, backend,
  backend_fingerprint, input_fingerprint
```
`requested_groups` is not in the key — including it would make each distinct group set its own isolated cache bucket, breaking the superset validity check. `schema_version` is not in the key — type ID changes affect the `input_fingerprint` directly, and algorithm changes are covered by `weaver_version`. The key is the same regardless of which groups are requested.

**`StrandCache` Protocol** signature:
```
get(key: StrandCacheKey, requested_groups: frozenset[str]) -> WeaveResult | None
put(key: StrandCacheKey, result: WeaveResult) -> None
```
`get` takes `requested_groups` as a separate argument so the implementation can perform the superset scan without exposing scan logic to callers. `put` uses `result.computed_groups` internally to index the entry.

**`InMemoryStrandCache`** stores `dict[StrandCacheKey, list[WeaveResult]]` — one list per base key, one entry per distinct `computed_groups` seen. `get` iterates the list and returns the first entry where `entry.computed_groups ⊇ requested_groups`. `put` appends or replaces the entry with the matching `computed_groups`.

**`ReviewQueueItem`** and **`ExecutionError`** are in `executor.py`:
```
ReviewQueueItem
  strand_set: StrandSet
  triggering_result: WeaveResult
  remaining_steps: tuple[CapabilityInvocation, ...]

ExecutionError
  strand_set: StrandSet
  error_type: str
  message: str
  step_index: int | None       None = preflight failure
  capability_id: str | None    None = preflight failure
```
`ExecutionError` is JSON-serializable. No raw `Exception` objects in `ExecutionResult.errors`. To resume from review: inject chosen candidate strands, build a braid from `remaining_steps`, call `executor.execute()` with that braid and the resolved `StrandSet`.

**Definition of done:**

- Every dataclass round-trips through `to_json()` / `from_json()` without data loss.
- `compute_cache_key` test: same `type_id`+`value`, different `provenance` → same `input_fingerprint`.
- `compute_cache_key` test: same `type_id`, different `value` → different `input_fingerprint`.
- `compute_cache_key` test: StrandSet with extra unrelated strands produces same `input_fingerprint` as a StrandSet with only the consumed types.
- `compute_cache_key` test: two calls with the same inputs but different `requested_groups` produce the same `StrandCacheKey`.
- `Capability.triggered_groups` test: requesting a lineage output triggers only the lineage group, not the core group.
- `Capability.outputs_to_compute` test: requesting Group A output does not include Group B outputs; requesting Group B output does not include Group A outputs.
- `InMemoryStrandCache` test: `get(key, {"core"})` returns a hit on a stored entry with `computed_groups={"core","lineage"}` (superset satisfied).
- `InMemoryStrandCache` test: `get(key, {"core","lineage"})` misses on a stored entry with `computed_groups={"core"}` (not a superset).
- `InMemoryStrandCache` test: two calls with the same base key but different `computed_groups` store two separate entries; the richer one is found first for a superset-satisfied lookup.
- `StrandSet.merge_result` test: `HIGHEST_CONFIDENCE` keeps higher-confidence strand; `FIRST_WINS` never overwrites; `LAST_WINS` always overwrites.
- `BaseWeaver._reorder_by_key` test: missing keys get `NO_MATCH` at the correct positions; existing keys appear in correct positions regardless of map iteration order.
- `ReviewQueueItem` round-trips through `to_json()` / `from_json()`.
- `ExecutionError` round-trips through `to_json()` / `from_json()`.
- `backend_fingerprint(backend)` is abstract — attempting to instantiate a concrete `BaseWeaver` subclass without implementing it raises `TypeError`.

**Does not include:** graph projection, pathfinding, execution, any real weaver.

---

## Phase 2 — `BraidRegistry` and `Braider`

**What:** Build the registry that collects weavers and projects their capabilities into a graph, and the braider that finds routes through it.

**Deliverables:**

- `registry.py` — `BraidRegistry`
  - `register(weaver)` — manual registration; runs manifest validation; raises `InvalidManifestError` on failure; primary MVP path
  - `get_weaver(weaver_id)` — lookup
  - `manifests()` — all loaded manifests
  - `build_graph()` — projected edge graph (networkx DiGraph or equivalent)
- `planner.py` — `Braider`
  - `plan(available_types: frozenset[str], target_types: frozenset[str], *, backend_policy)` → `Braid`
  - Dijkstra over single-input capabilities only
  - Coalesces edges from the same capability into one `CapabilityInvocation`
  - Topological sort of steps by data dependency
  - Per-invocation backend assignment: intersects `BackendPolicy` preference with `capability.backends`

**Graph projection rules:**

Only capabilities with `len(consumes) == 1` are projected into the MVP graph. Multi-input capabilities are registered but not added to the graph.

Each single-input capability with `consumes={A}` and `produces={B, C, D}` adds three directed edges: `A→B`, `A→C`, `A→D`, annotated with `(weaver_id, capability_id, cost)`.

**Coalescing rule:**

After Dijkstra, group all selected edges by `(weaver_id, capability_id, input_type)`. Each group becomes one `CapabilityInvocation` with the union of output types.

**Backend assignment rule (per invocation):**

1. Take the ordered preference list from `BackendPolicy` (e.g. `LOCAL_FIRST` → `["local","api"]`).
2. Filter to only backends declared in `capability.backends`.
3. If the filtered list is empty, raise `NoPlanError` immediately.
4. `primary_backend = filtered[0]`, `fallback_backends = tuple(filtered[1:])`.
5. Assign `fallback_on` from policy defaults, restricted to conditions involving backends actually in `fallback_backends`.

**Definition of done:**

- Registry test: two weavers registered, both appear in `manifests()`.
- Registry test: a capability with `len(consumes) == 2` is registered but does not appear as a graph edge.
- Registry test: manifest with empty `weaver_id` raises `InvalidManifestError` at `register()`.
- Registry test: manifest where a produce type appears in two output groups raises `InvalidManifestError`.
- Registry test: manifest where a produce type appears in no output group raises `InvalidManifestError`.
- Registry test: manifest with overlapping output groups raises `InvalidManifestError`.
- Registry test: manifest with `max_batch_size=0` raises `InvalidManifestError`.
- Braider test: `organism.name → {ncbi.taxon.id}` produces a single-step braid with `from_types={"organism.name"}`.
- Braider test: `available_types={"organism.name","sample.id","extra"}`, `target_types={"ncbi.taxon.id"}` → braid uses only `organism.name`; `from_types={"organism.name"}` (not `{"organism.name","sample.id","extra"}`).
- Braider test: `organism.name → {ncbi.taxon.id, ncbi.taxon.lineage, ncbi.taxon.rank}` produces a single `CapabilityInvocation` (coalesced), not three.
- Braider test: a two-hop path produces two steps in correct dependency order.
- Braider test: requesting a type that no weaver can produce raises `NoPathError`.
- Braider test: `LOCAL_FIRST` + capability with `backends=("local","api")` → `primary="local"`, `fallback=("api",)`.
- Braider test: `LOCAL_FIRST` + capability with `backends=("api",)` → `primary="api"`, `fallback=()`. No error — degrades gracefully.
- Braider test: `LOCAL_ONLY` + capability with `backends=("api",)` → raises `NoPlanError`.
- Braider test: a fake two-input capability is not reachable even if both consumed types are available.

**Does not include:** execution, caching, any real weaver.

---

## Phase 3 — `LocalExecutor`

**What:** Build the in-process async executor that runs a `Braid` against a list of `StrandSet`s.

**Deliverables:**

- `executor.py` — `LocalExecutor`, `ReviewPolicy`, `ErrorPolicy`, `ExecutionResult`
  - Preflight validation before any steps: entities missing `braid.from_types` go to `errors` with `MissingInputError`
  - Chunked processing (configurable `chunk_size`, default 10,000)
  - Guard 1 per step: already-satisfied entities pass through without weaver call or cache lookup
  - Cache split using group-superset validity rule; only misses reach `execute_batch`
  - Miss list split into sub-batches of at most `capability.max_batch_size` before calling `execute_batch`
  - Backend fallback loop per `CapabilityInvocation.fallback_backends` and `fallback_on`
  - `BackendConfigurationError` raises from `execute()` immediately, aborting the run
  - `ReviewPolicy.HALT` (default), `ALLOW_CONTINUE` (for OK+requires_review only), `RAISE`
  - `AMBIGUOUS` always goes to `review_queue` or raises — `ALLOW_CONTINUE` does not apply
  - `ErrorPolicy.RECORD_AND_CONTINUE` (default), `RAISE`
  - `confidence_threshold` check (default 0.0 = disabled), follows `ReviewPolicy`
  - `NO_MATCH` entities go to `unresolved`, not `errors`
  - Merges `WeaveResult` strands into `StrandSet` via `merge_result(policy=HIGHEST_CONFIDENCE)`
  - Builds `ReviewQueueItem` with `remaining_steps` on halt
  - Populates `ExecutionResult.resolved`, `.unresolved`, `.review_queue`, `.errors`

**Execution logic:**

Preflight (once):
1. For each entity, check `braid.from_types ⊆ entity.available_types()`. Failures → `errors` with `MissingInputError`.

Per step, per chunk:
2. Guard 1: already-satisfied entities pass through unchanged.
3. Cache split on remaining: `get(base_key, triggered_groups)`. Hits → route through the same result-handling path as fresh results (steps 8–13 below); no weaver call occurs.
4. Misses: split into sub-batches of at most `capability.max_batch_size`. Call `execute_batch` per sub-batch. Reassemble in order.
5. On `BackendConfigurationError`: raise from `execute()` immediately.
6. On `BackendUnavailable` per `fallback_on`: retry the **entire** miss batch on the next backend.
7. On `NO_MATCH`/`ERROR` per `fallback_on`: retry **only the affected entities** on the next backend. Keep results for OK/AMBIGUOUS entities from the current backend.
8. On `NO_MATCH` exhausted: entity → `unresolved`.
9. On `ERROR` exhausted: `RECORD_AND_CONTINUE` → `ExecutionError` in `errors`; `RAISE` → raise.
10. On `AMBIGUOUS`: entity → `review_queue` with remaining steps (or raise with `ReviewPolicy.RAISE`).
11. On `OK` + `requires_review=True` or `confidence < threshold`: apply `ReviewPolicy`.
12. Store result in cache. Merge strands into `StrandSet`.

After last step:
13. Active entities still in the set → `resolved`.

**Definition of done:**

- Executor test: 3 strand sets, all misses, all three land in `resolved`.
- Executor test: second pass with same inputs hits cache; `execute_batch` not called; all in `resolved`.
- Executor test: cache superset — first call requests `{ncbi.taxon.id}` (core only), second call requests `{ncbi.taxon.lineage}` → miss (stored `{"core"}` does not cover `{"core","lineage"}`).
- Executor test: a cached `NO_MATCH` result routes the entity to `unresolved` on the second pass; it does not land in `resolved`.
- Executor test: a cached `AMBIGUOUS` result routes the entity to `review_queue` on the second pass; `execute_batch` is not called.
- Executor test: preflight — entity missing `braid.from_types` goes to `errors` with `MissingInputError` before any step runs.
- Executor test: Guard 1 — entity already holding all output types skips the step; `execute_batch` not called for that entity.
- Executor test: `NO_MATCH` result → entity lands in `unresolved`, not `errors` or `resolved`.
- Executor test: `AMBIGUOUS` result with `HALT` → entity in `review_queue`; `ALLOW_CONTINUE` does not prevent this.
- Executor test: `AMBIGUOUS` result with `RAISE` → raises immediately.
- Executor test: `OK + requires_review=True` with `ALLOW_CONTINUE` → strands merged, entity continues and lands in `resolved`.
- Executor test: `ReviewQueueItem.remaining_steps` contains exactly the steps after the halting step.
- Executor test: `BackendConfigurationError` raises from `execute()` immediately; no entity recorded in `errors`.
- Executor test (fake multi-backend weaver): `BackendUnavailable` with `LOCAL_FIRST` → entire miss batch retried on API fallback.
- Executor test (fake multi-backend weaver): `WeaveStatus.ERROR` with `FallbackCondition.ERROR` in `fallback_on` → only the errored entity retried on the next backend; OK entities keep their results.
- Executor test (fake multi-backend weaver): mixed batch with one `NO_MATCH` entity and one `OK` entity; `FallbackCondition.NO_MATCH` in `fallback_on` → only the `NO_MATCH` entity is retried; the `OK` entity is not re-resolved.
- Executor test: `WeaveStatus.ERROR` with `RECORD_AND_CONTINUE` → `ExecutionError` in `errors`; rest of batch continues.
- Executor test: `ErrorPolicy.RAISE` → executor raises immediately; no `ExecutionResult` returned; entity not in `errors`.
- Executor test: capability with `max_batch_size=3`, 10 misses → `execute_batch` called 4 times (3+3+3+1); results reassembled in original order.
- Executor test: `len(resolved) + len(unresolved) + len(review_queue) + len(errors) == len(input_strand_sets)` for a mixed batch.
- Executor test: `ExecutionError` in `errors` is JSON-serializable (no raw exception objects).
- Executor test: `confidence_threshold=0.8`, strand with `confidence=0.75` → entity halted per `ReviewPolicy`.
- Executor test: `confidence_threshold` and `requires_review` are independent — entity with both conditions triggers halt only once; policy applied once.
- Executor test: batch of 25,000 with `chunk_size=10_000` processes in three chunks.

**Does not include:** any real weaver, Celery, HPC.

---

## Phase 4 — Migrate TaxonWeaver

**What:** Wrap the existing `TaxonomyResolverService` (from taxonbridge) as `NCBITaxonWeaver`. The existing service API is unchanged.

**Deliverables:**

- `taxon_weaver/weaver.py` — `NCBITaxonWeaver(BaseWeaver)`
  - `MANIFEST` with two capabilities: `ncbi.resolve_name` and `ncbi.resolve_taxid`
  - Output groups per capability as defined in `architecture.md` (`id`, `outputs` only — no `marginal_cost`, no `depends_on`)
  - `backends=("local", "api")` for both capabilities. The `local` backend wraps the SQLite `TaxonomyResolverService`; the `api` backend calls NCBI Datasets v2 (`https://api.ncbi.nlm.nih.gov/datasets/v2`). See `architecture.md` for endpoint mapping.
  - **The two backends can return slightly different results for the same name** — `local` uses the bundled DB + in-house rapidfuzz matching, `api` uses NCBI's own name matching (`taxon_suggest` exact + fuzzy). They are fallback-interchangeable, not identical. The `api` backend re-scores NCBI suggestions with the local rapidfuzz scoring so `confidence` is comparable. `backend` is part of the cache key, so local and api results are cached separately.
  - `api` backend specifics: `ncbi.resolve_name` → `taxon_suggest` (exact + fuzzy) for core, plus a second batched lineage lookup over the deduped union of ancestor taxids (Datasets `lineage` is taxids-only). Batches up to 1000 taxons/request. `BackendUnavailable` if the api backend is selected but not configured.
  - `backend_fingerprint(backend)` delegates to the selected strategy: `"local"` → `taxonomy_build_version` from `get_taxonomy_build_info()`; `"api"` → Datasets v2 service id (`"datasets-v2"`/`"live"`)

**Package layout (strategy + shared mapper + factory):**

- `taxon_weaver/backends/base.py` — `ResolutionBackend` (taxon-package interface; implements core's generic `BackendStrategy`): `name`, `is_configured()`, `fingerprint()`, and an `async resolve(queries, *, need_lineage) -> list[TaxonMatch]` returning input-order results.
- `taxon_weaver/backends/local.py` — `LocalTaxonomyBackend`: wraps `TaxonomyResolverService`; `threading.local()` service per thread, lazily created; `asyncio.to_thread()`; `resolve_batch()` once per batch → `TaxonMatch`. `BackendConfigurationError` if `db_path` does not exist or is not valid SQLite.
- `taxon_weaver/backends/datasets_v2.py` — `DatasetsV2Backend`: async HTTP to Datasets v2; `taxon_suggest` (exact + fuzzy) + a second batched lineage lookup over the deduped union of ancestor taxids (Datasets `lineage` is taxids-only); ≤1000 taxons/request; re-scores suggestions with the local rapidfuzz scoring for comparable `confidence`; uses `_reorder_by_key` to realign keyed responses.
- `taxon_weaver/intermediate.py` — `TaxonMatch`, `LineageEntry`, `CandidateMatch` (taxon-specific; never leak into core).
- `taxon_weaver/mapper.py` — the single `TaxonMatch -> WeaveResult` mapper: identical strand shapes across backends, status mapping, `computed_groups`.
- `taxon_weaver/weaver.py` — `NCBITaxonWeaver(BackendDispatchWeaver)`: holds `dict[str, ResolutionBackend]`; `execute_batch` selects by `backend`, raises `BackendUnavailable` if absent/unconfigured, runs the mapper.
- `taxon_weaver/factory.py` — `build_ncbi_weaver(config)`: configures `local` and `api` independently; a missing backend is simply not registered (does **not** poison the weaver when fallback covers it); surfaces as `BackendUnavailable` only if selected with no fallback.

- Manual registration is the MVP path; no `pyproject.toml` entry point required yet:
  ```python
  registry.register(build_ncbi_weaver(config))
  ```

**Strand mapping from `TaxonMatch` (both backends normalize to this; field names follow `ResolveResult`):**

| ResolveResult field | Strand type_id | Group |
|---|---|---|
| `matched_taxid` | `ncbi.taxon.id` | core |
| `matched_name` | `organism.scientific_name` | core |
| `matched_rank` | `ncbi.taxon.rank` | core |
| `lineage[-2].taxid` | `ncbi.taxon.parent_id` | core |
| `match_type` (str) | `ncbi.taxon.match_type` | core |
| `review_required` | `ncbi.taxon.review_required` | core |
| `lineage` (list of dicts) | `ncbi.taxon.lineage` | lineage |

Confidence: `result.score / 100.0` when score is not None; `1.0` for exact matches.

**`computed_groups` contract:** when only the core group was triggered externally, the weaver runs only the name resolution row fetch and sets `computed_groups={"core"}`. When the lineage group was triggered, the weaver runs both the row fetch and the lineage cache lookup, and sets `computed_groups={"core","lineage"}` — because the weaver always computes core internally as part of computing lineage. This is the correct and accurate report; the executor stores it and uses it for future cache hits.

**`WeaveResult.status` mapping:**

| ResolveResult.status | WeaveStatus | Notes |
|---|---|---|
| RESOLVED\_\* | OK | — |
| SUGGESTED\_FUZZY\_UNIQUE | OK | confidence < 1.0, requires\_review=True |
| AMBIGUOUS\_\* | AMBIGUOUS | candidates populated |
| MANUAL\_REVIEW\_REQUIRED | AMBIGUOUS | candidates populated if present |
| UNRESOLVED\_NO\_MATCH | NO\_MATCH | — |
| UNRESOLVED\_VAGUE\_LABEL | NO\_MATCH | warning added |
| CONFIRMED\_BY\_USER | OK | — |
| REJECTED\_BY\_USER | NO\_MATCH | — |

**Definition of done:**

- `WeaverOrderContractTests` mixin passes for `NCBITaxonWeaver` on a real test DB.
- `execute_batch` for `ncbi.resolve_name` with 100 names issues exactly one `resolve_batch` call.
- `backend_fingerprint("local")` returns a non-`"unknown"` string when backed by a real DB; `backend_fingerprint("api")` returns the Datasets v2 service id.
- Requesting only `ncbi.taxon.id` (core group): lineage cache not read; `computed_groups={"core"}`.
- Requesting `ncbi.taxon.lineage` (lineage group): both groups computed; `computed_groups={"core","lineage"}`.
- `TypeError` raised when `db_path` is omitted at construction.
- `BackendConfigurationError` raised at construction when `db_path` points to a nonexistent file or invalid database.
- Each thread in a thread pool gets its own SQLite connection (test with concurrent `asyncio.to_thread` calls).
- Existing `TaxonomyResolverService` tests pass without modification.
- `backends == ("local", "api")` declared on both capabilities.
- `api` backend: `execute_batch` for `ncbi.resolve_name` issues a bounded number of HTTP calls (one `taxon_suggest` batch per ≤1000 names, plus one batched lineage lookup when the lineage group is requested) — mock the HTTP client; no live network in tests.
- `api` backend: a name with one exact `taxon_suggest` hit → `OK`; multiple/fuzzy hits → `AMBIGUOUS` with candidates; zero hits → `NO_MATCH`.
- `api` backend: confidence on api-produced strands is computed with the same rapidfuzz scoring as the local backend.
- `BackendUnavailable` raised when the `api` backend is selected but not configured.
- Divergence is tolerated: `local` and `api` may return different taxids for the same name; the contract asserts each backend's result is internally valid, not that they match each other.

---

## Phase 5 — End-to-End Integration Test

**What:** A full integration test that exercises the complete stack: registry → braider → executor → weaver → cache.

**Scenario:** 1,000 organism names → `{ncbi.taxon.id, ncbi.taxon.lineage}` using the real test database.

**Assertions:**

1. Braider produces a `Braid` with a single `CapabilityInvocation` for `ncbi.resolve_name` requesting both types (coalesced).
2. Executor calls `execute_batch` exactly once for 1,000 names.
3. Each `StrandSet` in `resolved` contains both `ncbi.taxon.id` and `ncbi.taxon.lineage`.
4. `len(resolved) + len(unresolved) + len(review_queue) + len(errors) == 1000`.
5. Names with no NCBI match land in `unresolved`, not `errors`.
6. Second run with same inputs: zero `execute_batch` calls (all cache hits); all previously resolved names land in `resolved` again.
7. Third run requesting only `{ncbi.taxon.rank}`: zero `execute_batch` calls (core group cached from run 2, superset satisfied).
8. **Regression — superset correctness:** a fresh run requesting only `{ncbi.taxon.id}` (caches `{"core"}`) followed by a run requesting `{ncbi.taxon.lineage}` calls `execute_batch` again (`{"core"} ⊄ {"core","lineage"}`).
9. **Guard 1 regression:** inject 10 entities with `ncbi.taxon.id` already present. Those 10 skip `ncbi.resolve_name` entirely; their `execute_batch` call count is zero.
10. **Preflight regression:** inject 5 entities with no `organism.name` strand. Those 5 land in `errors` with `MissingInputError` before any step runs; remaining 995 proceed normally.
11. **Backend assignment regression:** register a fake weaver (not `NCBITaxonWeaver`) with `backends=("api",)` only. Plan with `LOCAL_ONLY` raises `NoPlanError`. Plan with `LOCAL_FIRST` succeeds with `primary_backend="api"`, `fallback_backends=()`.

---

## Contract Tests (Ship with `braidworks-core`)

These test mixins are importable by any weaver author and must be included in every weaver's test suite.

### `WeaverOrderContractTests`

Parameterized by: `weaver`, `capability_id`, `sample_strand_sets` (at least 5 items with distinct input values), `minimal_outputs`.

Verifies:
- `len(execute_batch(...)) == len(sample_strand_sets)`
- Result at index `i` corresponds to input at index `i`
- Reversing the input list reverses the output list

### `CacheFingerprintTests`

Verifies:
- Same `(type_id, value)`, different `provenance` → same `input_fingerprint`
- Same `type_id`, different `value` → different `input_fingerprint`
- StrandSet with extra unrelated strands → same `input_fingerprint` as minimal StrandSet
- Different `requested_groups`, same everything else → same `StrandCacheKey`
- Same inputs, different `backend_fingerprint` → different `StrandCacheKey`
- Same inputs, different `weaver_version` → different `StrandCacheKey`
- Same inputs, different `weaver_id` → different `StrandCacheKey`
- `computed_groups={"core","lineage"}` satisfies a lookup with `requested_groups={"core"}`
- `computed_groups={"core"}` does not satisfy a lookup with `requested_groups={"core","lineage"}`
- Two `put()` calls with same base key but different `computed_groups` store two entries; both retrievable by appropriate `requested_groups`

---

## Dependency Graph

```
braidworks-core
  └── stdlib + networkx only

taxon_weaver (renamed from taxonbridge)
  ├── braidworks-core
  └── existing deps (rapidfuzz, etc.)

braidworks-arq
  ├── braidworks-core
  └── arq, redis

(future) uniprot-weaver
  └── braidworks-core
```

---

## What Is Not In Scope for MVP

The following are architectural decisions already reflected in the interfaces but not implemented:

- Multi-input capability activation in the braider (capabilities declared in manifest, not in graph)
- Set-based braiding
- Entry-point discovery (`discover()`) — deferred until plugin configuration is resolved
- `BackendPolicy.ANY` — deferred until per-backend cost model exists
- Celery or HPC executor
- Redis cache
- Parallel step execution (independent steps run serially for now)
- Type schema versioning
- Calibrated confidence

None of these require interface changes to implement later.
