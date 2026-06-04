# Braidworks Architecture

Braidworks is the framework layer that turns TaxonWeaver into one member of a composable network of biological data resolvers. Each resolver is a **Weaver**. Weavers declare what data types they consume and produce. A central registry builds a graph from those declarations. A braider finds routes through the graph. An executor runs the braid.

The goal is to make queries like "I have an organism name, I want a UniProt proteome ID" work automatically by routing through whichever weavers can bridge the gap, without the caller knowing how.

---

## Guiding Principles

- **Contracts over magic.** Every piece of data is a typed, serializable Strand. Every operation is a declared Capability. Nothing flows implicitly.
- **Plan first, execute second.** Planning is pure computation. Execution is side-effectful. They are separate objects with separate interfaces, so the execution backend can be swapped without touching the braider.
- **Batch is the primary path.** Single-item resolution is a special case of batch. Weavers are always called through `execute_batch`. The default implementation loops serially; weavers that support real batch override it.
- **Failures are values.** A no-match, an ambiguous result, and a review flag are all represented in `WeaveResult`, not raised as exceptions. Configuration errors are run-level failures that abort the executor. Genuine per-entity weaver failures are `WeaveStatus.ERROR`.
- **Lightweight by default.** No required infrastructure. In-process async execution with an in-memory cache is the default. Redis, Celery, and HPC are optional backends that satisfy the same interfaces.

---

## Core Abstractions

### Strand

The atomic unit of data in Braidworks. Immutable and JSON-serializable.

```python
@dataclass
class Strand:
    type_id: str
    value: str | int | float | list | dict | None
    confidence: float = 1.0          # normalized quality score [0.0, 1.0]
    provenance: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
```

Strand is treated as immutable by convention. `frozen=True` is not used because `value` can be a `list` or `dict` and `metadata` is a `dict`; `frozen=True` would only be shallow and give a false guarantee. Nothing in Braidworks mutates a Strand after construction.

Callers creating input strands need only `type_id` and `value`: `Strand("organism.name", "Homo sapiens")`. Weavers populate `confidence` and `provenance` on produced strands.

**Confidence is a quality score, not a calibrated probability.** A fuzzy match at 85/100 maps to `0.85` as a heuristic for downstream filtering and planning decisions. It does not mean there is an 85% chance the answer is correct. Weavers that have actual calibration data expose `calibrated_probability` separately in `metadata`.

### Type ID Naming Convention

Type IDs are namespaced strings: `{namespace}.{entity}.{attribute}`. Shared cross-weaver types carry no namespace prefix: `organism.name`. Weaver-specific types are namespaced: `ncbi.taxon.id`, `uniprot.proteome.id`.

**Scalar vs. collection types are distinguished by suffix:**

- Singular suffix → single scalar value: `ncbi.taxon.id`, `organism.scientific_name`, `ncbi.taxon.rank`
- Plural suffix → list value: `ncbi.assembly.ids`, `uniprot.proteome.ids`

The `value` field of a collection strand is always a `list`. A type called `uniprot.proteome.id` (singular) means exactly one proteome was selected. A type called `uniprot.proteome.ids` (plural) means a list of proteomes is returned. This distinction must be made at type definition time, not resolved ambiguously at runtime. When uncertain which is appropriate, define the plural type and let callers filter.

Type IDs are the extension point for schema evolution — versioning appended as a suffix if needed.

---

### StrandSet

The collection of strands currently known for one entity or query context. This is what the braider reasons over. Mutable during execution; the executor owns it once handed over.

```
StrandSet
  entity_id: str                             stable identifier for this entity
  _strands: dict[str, Strand]                one strand per type_id
  requires_review: bool                      True if any result required review
  warnings: list[str]
  errors: list[str]
```

Key operations:
- `from_strands(entity_id, strands)` — class method; primary constructor for callers; accepts a list of `Strand`s
- `has(type_id)`, `get(type_id)` — lookup
- `available_types()` → `frozenset[str]` — what the braider sees
- `merge_result(result, policy)` — adds strands from a `WeaveResult` according to `MergePolicy`

The internal `_strands: dict[str, Strand]` field is not part of the public API. Use `from_strands()` to construct and `get()`/`has()` to read.

**MergePolicy** controls what happens when a type already exists in the set:
- `HIGHEST_CONFIDENCE` — keep whichever strand scores higher (default)
- `FIRST_WINS` — never overwrite
- `LAST_WINS` — always overwrite

One strand per type_id is correct for scalar types. Collection types (`ncbi.assembly.ids`) naturally store their list as the strand's `value` — no special multi-strand handling is needed.

StrandSets are JSON-serializable for HPC step boundaries. Each HPC step deserializes a fresh copy; mutability during local execution does not affect this.

---

### OutputGroup

Declares which outputs of a Capability are computed together from the same underlying operation. Requesting any output in a group triggers the whole group; requesting outputs from no group means that group is entirely skipped.

```
OutputGroup
  id: str                                    unique within a Capability
  outputs: frozenset[str]
```

The weaver is responsible for its own internal execution ordering. If computing one group requires another group to run first internally (e.g. TaxonWeaver always resolves the name before fetching lineage), that is entirely the weaver's concern. The weaver reports everything it actually computed in `WeaveResult.computed_groups`, which the cache uses for validity checks.

**For TaxonWeaver `ncbi.resolve_name`:**

```
OutputGroup id="core"
  outputs = {ncbi.taxon.id, organism.scientific_name, ncbi.taxon.rank,
              ncbi.taxon.parent_id, ncbi.taxon.match_type, ncbi.taxon.review_required}
  — single DB row fetch (taxon_names JOIN taxa)

OutputGroup id="lineage"
  outputs = {ncbi.taxon.lineage}
  — separate lineage_cache lookup; always computes core internally first
```

Requesting only `ncbi.taxon.id` triggers only `core`; the weaver skips the lineage lookup entirely. Requesting `ncbi.taxon.lineage` triggers only `lineage` from the executor's perspective, but the weaver internally runs the name resolution first and reports `computed_groups={"core","lineage"}`. Those core strands are present in the result even though only lineage was requested.

---

### Capability

One declared operation that a Weaver can perform. Consumes one or more strand types, produces one or more strand types.

```
Capability
  id: str                                    "ncbi.resolve_name"
  consumes: frozenset[str]                   required input strand type_ids
  produces: frozenset[str]                   output type_ids this capability can generate
  output_groups: tuple[OutputGroup, ...]
  backends: tuple[str, ...]                  ("local",), ("api",), ("local", "api")
  max_batch_size: int | None                 None = no limit; enforced by executor
  cost: float = 1.0                          edge weight for Dijkstra; default 1.0 for all MVP capabilities
```

The capability exposes two derived queries used by the executor:
- `triggered_groups(requested)` — which OutputGroups contain at least one of the requested outputs.
- `outputs_to_compute(requested)` — union of all triggered group outputs, intersected with `produces`.

A weaver **must** produce every type in `outputs_to_compute(requested_outputs)`. It **must not** compute types in groups that were not triggered externally. The weaver may compute additional types internally as part of satisfying a triggered group, and should report them in `computed_groups` so the cache captures them for future requests.

---

### WeaverManifest

Static declaration of a weaver's capabilities. Loadable from the entry-point class without instantiation.

```
WeaverManifest
  weaver_id: str
  version: str                               semver
  capabilities: tuple[Capability, ...]
```

The registry reads manifests to build the capability graph before any weaver is instantiated. Manifests are declared as class-level constants on the weaver class.

---

### WeaveResult

What one capability invocation returns. Always exactly one per input StrandSet. Never one per match; multiple candidates live inside the result.

```
WeaveResult
  capability_id: str
  weaver_version: str                        from WeaverManifest.version at call time; feeds StrandCacheKey.weaver_version
  backend_used: str                          actual backend: "local" or "api", never "any"
  computed_groups: frozenset[str]            group ids actually computed, including internal deps
  status: WeaveStatus
  strands: tuple[Strand, ...]                empty if NO_MATCH or ERROR
  candidates: tuple[CandidateResult, ...]   populated when AMBIGUOUS
  warnings: tuple[str, ...]
  errors: tuple[str, ...]
  requires_review: bool
```

`computed_groups` must reflect every group the weaver actually computed, including groups computed internally as dependencies. This is what the cache uses for validity checks.

**WeaveStatus values:**
- `OK` — resolved, strands populated
- `NO_MATCH` — nothing found; strands empty
- `AMBIGUOUS` — multiple candidates; strands empty, candidates populated, `requires_review=True`
- `ERROR` — weaver-side per-entity failure; strands empty, errors populated

**CandidateResult** holds one alternative when the result is ambiguous:
```
CandidateResult
  strands: tuple[Strand, ...]
  confidence: float
  metadata: dict[str, Any]
```

**`requires_review` vs `confidence` are distinct and must not substitute for each other.** `confidence` is a continuous quality score used by the braider and callers for filtering. `requires_review` is a hard boolean gate: the executor will not automatically continue a chain when this is True unless the caller explicitly set `ReviewPolicy.ALLOW_CONTINUE`. A result can have `confidence=0.95` and still require review (a synonym match that policy mandates for curation). A result can have `confidence=0.60` and not require review if the caller opted in to low-confidence auto-resolution.

All WeaveResult fields are JSON-serializable.

---

### BaseWeaver

The interface every weaver implements.

```python
class BaseWeaver(ABC):
    MANIFEST: ClassVar[WeaverManifest]

    @abstractmethod
    def backend_fingerprint(self, backend: str) -> str:
        """Fingerprint of the named backend's data state. Per-backend by design.
        Used in cache key construction. Must be overridden — there is no default.
        Generalizes the old `dataset_version()`: not every backend is a dataset.
        Return a stable, version-specific string for versioned datasets:
          backend_fingerprint("local") -> "ncbi-taxonomy-2024-03-16"
        Return an explicit string for unversioned or live sources:
          backend_fingerprint("api")   -> "datasets-v2" or "live"
        Never return "unknown" — that silently disables cache invalidation.
        """

    @abstractmethod
    async def execute(
        self,
        capability_id: str,
        strand_set: StrandSet,
        *,
        requested_outputs: frozenset[str],
        backend: str,                          # always "local" or "api"
    ) -> WeaveResult: ...

    async def execute_batch(
        self,
        capability_id: str,
        strand_sets: list[StrandSet],
        *,
        requested_outputs: frozenset[str],
        backend: str,
    ) -> list[WeaveResult]:
        # Default: serial loop. Override for true batch.
        ...
```

**`execute_batch` hard contract:**
- Returns exactly one `WeaveResult` per input `StrandSet`.
- Results are in the same order as the input list.
- If an input has no match, that position gets `WeaveResult(status=NO_MATCH)`.
- If an input is ambiguous, that position gets `WeaveResult(status=AMBIGUOUS, candidates=...)`.
- If an input fails (weaver-side error), that position gets `WeaveResult(status=ERROR)`.
- Never return fewer results than inputs. Never reorder.

**Error classification:**

- `BackendConfigurationError` — a declared, configured backend is broken at runtime (corrupt DB file, invalid credentials, unreachable host). Run-level failure: the executor raises it immediately and aborts. Never per-entity, never triggers fallback.
- `BackendUnavailable` — a declared backend is not available in this specific instance (e.g. a multi-backend weaver class instantiated without a particular backend's configuration). The executor may fall back to the next backend if `FallbackCondition.BACKEND_UNAVAILABLE` is in `fallback_on`. This is distinct from `InvalidManifestError`: the manifest correctly declares a backend the class implements; it is just not configured in this instance.
- `WeaveStatus.ERROR` — a per-entity failure (API timeout, malformed response, lookup failure for a specific input). Controlled by `ErrorPolicy` after fallbacks are exhausted.

**On `NCBITaxonWeaver` for MVP:** the weaver declares two backends, `("local", "api")`. `db_path` is required at construction for the `local` backend. Omitting it raises `TypeError` immediately. `BackendConfigurationError` is raised if `db_path` is provided but the file does not exist or is not a valid SQLite database. The `api` backend (NCBI Datasets v2) is configured separately; if a backend is selected but not configured in this instance it raises `BackendUnavailable`, which can trigger fallback when `FallbackCondition.BACKEND_UNAVAILABLE` is in `fallback_on`.

**Backends are not guaranteed to agree.** The `local` backend resolves names with the bundled SQLite DB and the in-house rapidfuzz fuzzy matcher; the `api` backend resolves against NCBI Datasets v2, whose name matching and candidate generation are NCBI's own. For the same input name the two backends **can return slightly different results** — a different chosen taxid, different candidates, or a different `backend_fingerprint`. This is expected and acceptable: backends are fallback-interchangeable, not bit-identical. To keep `confidence` comparable across backends, the api backend re-scores NCBI's returned suggestions with the same rapidfuzz scoring the local backend uses. This divergence is exactly why both `backend` and `backend_fingerprint` are part of the `StrandCacheKey` — a local result and an api result for the same input are cached as distinct entries.

**`_reorder_by_key(results_map, original_keys, ...)`** is a static helper for weavers whose underlying API returns results keyed by some identifier rather than in input order. The weaver builds `{key: WeaveResult}` from the API response and passes it along with the original key order. Missing keys get a `NO_MATCH` result at the correct position. Does not handle duplicate keys — the weaver must de-duplicate first.

**Weaver state is lazily initialized.** Connections are created on first `execute()` call, not in `__init__`. A weaver instantiated on a new machine or process connects on demand.

**SQLite backend notes** (applies to TaxonWeaver and any future local-DB weavers):
- Open connections as read-only where possible.
- Use `threading.local()` for one connection per thread. A single shared connection across threads is not safe without a lock, and a lock destroys concurrency.
- SQLite is not appropriate on HPC network filesystems (NFS). On HPC, use a locally-copied DB or a different backend.
- SQLite is one backend implementation detail of TaxonWeaver, not a Braidworks dependency.

---

## StrandCache

### StrandCacheKey

The cache key captures everything that determines whether a cached result is still valid, **excluding the requested groups**:

```
StrandCacheKey  (base key — no group information)
  weaver_id: str                     which weaver produced it (two weavers may share a capability_id)
  weaver_version: str                from WeaverManifest.version; algorithm changes invalidate old entries
  capability_id: str
  backend: str                       local and API can return different data
  backend_fingerprint: str           per-backend, from weaver.backend_fingerprint(backend)
  input_fingerprint: str             sha256 of {consumed_type_id: value} — see below
```

**Requested outputs and computed groups are deliberately absent from the key.** They are not ignored — they are handled by the *separate* superset validity check (see below), where `computed_groups` lives on the stored entry and `get(key, requested_groups)` performs the `⊇` match. Putting either in the key would make each distinct group set its own isolated cache bucket, breaking superset reuse entirely (request `lineage`, cache `{"core","lineage"}`, later request `core` → must still hit). Type ID changes affect the input fingerprint directly; algorithm changes are covered by `weaver_version`. No additional schema versioning field is needed.

**Input fingerprint hashes only the strand types listed in `capability.consumes`, not the full StrandSet.** Extra strands accumulated from prior steps must not cause a cache miss.

```
fingerprint_inputs = {
    type_id: strand_set.get(type_id).value
    for type_id in capability.consumes
}
```

Provenance is excluded. The same value arriving via different upstream paths must share a cache entry.

**`backend_fingerprint` is mandatory for correctness and is per-backend.** A TaxonWeaver `local` backend on a 2024 NCBI dump and one on a 2026 dump must not share entries; likewise a `local` result and an `api` result for the same input are distinct (different `backend` *and* different `backend_fingerprint`). All weavers must implement `backend_fingerprint(backend)` — it replaces the old backend-blind `dataset_version()`. The executor evaluates it per-backend: with `invocation.primary_backend` for the pre-check key and with `result.backend_used` for the post-execution key, so a result is always cached under the fingerprint of the backend that actually produced it.

### Cache Validity and Output Groups

A cached entry is valid for the current request only when:

```
cached_result.computed_groups ⊇ triggered_groups(requested_outputs)
```

Because `requested_groups` is not part of the key, a single base key may have multiple stored entries — one per distinct `computed_groups` set seen across past calls. The cache `get` method scans all entries for the matching base key and returns the first where the superset condition holds.

Example lifecycle for one organism name:
1. First call requests `{ncbi.taxon.id}` → triggers `{"core"}` → weaver computes core → result stored with `computed_groups={"core"}`.
2. Second call requests `{ncbi.taxon.lineage}` → triggers `{"lineage"}` → lookup: `{"core"} ⊇ {"lineage"}`? No → miss → weaver computes lineage (and core internally) → result stored with `computed_groups={"core","lineage"}`.
3. Third call requests `{ncbi.taxon.id}` → triggers `{"core"}` → lookup: `{"core"} ⊇ {"core"}`? Yes → hit on first entry. Also `{"core","lineage"} ⊇ {"core"}`? Yes → either entry is valid.
4. Fourth call requests `{ncbi.taxon.rank}` (also in core) → triggers `{"core"}` → hit on first entry.

### StrandCache Interface

`StrandCache` is a Protocol. The `get` method takes `requested_groups` separately from the base key so the implementation can perform the superset scan without exposing the scan logic to callers.

```
StrandCache (Protocol)
  get(key: StrandCacheKey, requested_groups: frozenset[str]) -> WeaveResult | None
  put(key: StrandCacheKey, result: WeaveResult) -> None
  # result.computed_groups is used internally by put() to index the entry
```

The in-memory implementation stores `dict[StrandCacheKey, list[WeaveResult]]` — a list per base key, one entry per distinct `computed_groups` encountered. `get` iterates the list and returns the first entry satisfying the superset condition. `put` appends or replaces the entry with the matching `computed_groups`.

TTL enforcement is deferred until a Redis backend is implemented. The interface does not include `ttl` — adding a parameter that the only implementation ignores is misleading.

---

## Backend Policy and Fallback

Backend selection is the braider's responsibility, not the weaver's. Each `CapabilityInvocation` carries an explicit primary backend and an ordered fallback list. The executor controls fallback; the weaver never silently degrades.

```
CapabilityInvocation
  weaver_id: str
  capability_id: str
  input_types: frozenset[str]
  output_types: frozenset[str]
  primary_backend: str
  fallback_backends: tuple[str, ...]
  fallback_on: frozenset[FallbackCondition]
```

**FallbackCondition values:**
- `NO_MATCH` — try next backend if result status is `NO_MATCH`
- `ERROR` — try next backend if result status is `ERROR`
- `BACKEND_UNAVAILABLE` — try next backend if weaver raises `BackendUnavailable`

`BackendConfigurationError` is never in `fallback_on`. It aborts the run.

**BackendPolicy** controls how the braider assigns primary and fallbacks — but the braider must intersect the policy preference with `capability.backends` before assigning. A capability that only declares `("api",)` cannot have `primary_backend="local"` regardless of what the policy prefers.

**Braider backend assignment rule (per invocation):**

1. Take the ordered preference list from `BackendPolicy` (e.g. `LOCAL_FIRST` → `["local", "api"]`).
2. Filter the preference list to only backends declared in `capability.backends`.
3. If the filtered list is empty, raise `NoPlanError` at planning time — not at runtime.
4. Assign `primary_backend = filtered[0]`, `fallback_backends = tuple(filtered[1:])`.
5. Assign `fallback_on` from the policy defaults (see table below), but only for conditions that involve backends actually in `fallback_backends`.

| Policy | Preference order | FallbackOn |
|---|---|---|
| `LOCAL_ONLY` | [local] | — |
| `API_ONLY` | [api] | — |
| `LOCAL_FIRST` | [local, api] | NO\_MATCH, BACKEND\_UNAVAILABLE |
| `API_FIRST` | [api, local] | NO\_MATCH, BACKEND\_UNAVAILABLE |

Example: `LOCAL_FIRST` + capability with `backends=("api",)` → preference list `["local","api"]` filtered to `["api"]` → `primary_backend="api"`, `fallback_backends=()`, `fallback_on={}`. No `NoPlanError` because "api" is available; the policy degrades gracefully.

Example: `LOCAL_ONLY` + capability with `backends=("api",)` → preference list `["local"]` filtered to `[]` → `NoPlanError` at plan time.

---

## BraidRegistry

Collects weavers and their manifests. Builds the projected capability graph used by the braider.

**Manual registration is the MVP path:**

```python
registry = BraidRegistry()
registry.register(NCBITaxonWeaver(db_path="/data/taxonomy.db"))
```

This is explicit and handles the configuration problem directly — each weaver is instantiated with its required parameters before being registered. Entry-point discovery (`discover()`) is deferred: instantiating a weaver from an entry point with no configuration requires a plugin-configuration mechanism (env vars, config files, factory functions) that is a separate unsolved problem. When that is resolved, `discover()` becomes viable. For now, manual registration is the only supported path.

**Manifest validation** runs at `register()` time. A manifest that fails validation raises `InvalidManifestError` and is not registered. Rules:

```
- weaver_id is non-empty
- version is non-empty
- capability ids are unique within the weaver
- each capability.consumes is non-empty
- each capability.produces is non-empty
- each capability.backends is non-empty
- output group ids are unique within a capability
- every output group output type is in capability.produces
- every type in capability.produces appears in exactly one output group (no gaps, no overlaps)
- max_batch_size is None or > 0
- cost >= 0
```

The "every produces type in exactly one group" rule is the most important: it makes `triggered_groups()` and `outputs_to_compute()` unambiguous. A weaver with an orphaned produce type (in `produces` but no group) or a duplicated type (in two groups) is rejected at registration, not at query time.

**Graph projection (MVP):**

Only single-input capabilities (`len(consumes) == 1`) are projected into the MVP graph. Multi-input capabilities are stored in the manifest and registered, but not added to the graph until the set-based braider is implemented.

A standard directed graph edge `A → C` implies A alone is sufficient for C. There is no correct way to represent `{A, B} → C` in a plain directed graph without AND-node semantics. Omitting multi-input capabilities from the MVP graph entirely is safer than projecting them incorrectly.

Each single-input capability with `consumes={A}` and `produces={B, C, D}` adds three directed edges: `A→B`, `A→C`, `A→D`, all annotated with `(weaver_id, capability_id, cost)`.

---

## Braider

Takes the set of currently available strand types and the set of desired target types, and returns a serializable `Braid`.

```python
def plan(
    available_types: frozenset[str],
    target_types: frozenset[str],
    *,
    backend_policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
) -> Braid
```

```
Braid
  steps: tuple[CapabilityInvocation, ...]    ordered; each step may expand the StrandSet
  from_types: frozenset[str]                 minimal required starting types — see below
  to_types: frozenset[str]
```

`Braid` is fully JSON-serializable. This is the serialization boundary for HPC: the coordinator plans once and ships the braid to each worker node.

**The braider takes `frozenset[str]`, not a `StrandSet`.** The braider is entity-agnostic — it only needs to know which strand types are available. Callers with a `StrandSet` pass `strand_set.available_types()`.

**`from_types` is the minimal required starting set, not all of `available_types`.** It is computed as the union of all `step.input_types` across the braid minus the union of all `step.output_types` — the types that must arrive from outside the braid. If the caller passes `available_types={"organism.name", "sample.id", "random.note"}` but the braid only uses `"organism.name"`, then `from_types={"organism.name"}`. The executor preflight checks `braid.from_types ⊆ entity.available_types()`, so an entity missing `sample.id` but having `organism.name` passes correctly. Echoing back all of `available_types` would break this.

**Both `available_types` and `target_types` are `frozenset[str]`.** There is no single-target overload in the core.

### MVP Planning Algorithm

1. Only single-input capabilities are in the graph (multi-input not projected).
2. For each target type not already in `available_types`, run Dijkstra from `available_types` to the target.
3. Collect all `(weaver_id, capability_id, input_type, output_type)` tuples from all paths.
4. Group by `(weaver_id, capability_id, input_type)`. Each group becomes one `CapabilityInvocation` with the union of `output_types`.
5. Topological sort on data dependencies (step N's outputs feed step N+1's inputs).
6. Per invocation: intersect `BackendPolicy` preference with `capability.backends` to assign `primary_backend`, `fallback_backends`, and `fallback_on`. Raise `NoPlanError` if no valid backend exists.

### Future Braider

Works over strand sets rather than single source types. Activates multi-input capabilities when all consumed types are present. The `Braid` interface is identical — only the braider internals change.

---

## Executor

Runs a `Braid` against a list of `StrandSet`s.

```
ReviewQueueItem
  strand_set: StrandSet                      state at halt
  triggering_result: WeaveResult             the result that caused the halt
  remaining_steps: tuple[CapabilityInvocation, ...]   steps not yet run for this entity

ExecutionError
  strand_set: StrandSet                      state at failure
  error_type: str                            exception class name
  message: str                               human-readable description
  step_index: int | None                     which step failed (None = preflight)
  capability_id: str | None                  which capability failed (None = preflight)

ExecutionResult
  resolved:     list[StrandSet]              target strands produced; braid ran to completion
  unresolved:   list[tuple[StrandSet, WeaveResult]]   braid ran but ended in NO_MATCH
  review_queue: list[ReviewQueueItem]        human decision required
  errors:       list[ExecutionError]         structural/technical failure with RECORD_AND_CONTINUE
```

`ExecutionError` is JSON-serializable. It captures the useful information from a failure without carrying a non-serializable Python exception object, which matters for future Celery and HPC execution where results are transmitted across process boundaries.

These four buckets are mutually exclusive and exhaustive. Every entity in the input batch ends up in exactly one.

- `resolved` — all requested target types were found or already present. StrandSet contains them.
- `unresolved` — the braid ran but a step returned `NO_MATCH` with no remaining fallbacks. Valid biological outcome ("we searched and found nothing"), not an error.
- `review_queue` — a step returned `AMBIGUOUS` or `OK + requires_review=True` with `ReviewPolicy.HALT`. The `ReviewQueueItem` includes `remaining_steps` so the caller can resume: inject chosen strands, build a braid from `remaining_steps`, call `execute()` again.
- `errors` — a structural failure recorded under `ErrorPolicy.RECORD_AND_CONTINUE`: preflight validation failure (`MissingInputError`) or `WeaveStatus.ERROR` after all backends exhausted.

`ErrorPolicy.RAISE` raises a Python exception immediately and aborts execution. No `ExecutionResult` is returned in that case; the entity is not added to `errors`.

`BackendConfigurationError` is a run-level exception — it also aborts immediately. No `ExecutionResult` is returned.

`sum(len(r) for r in [resolved, unresolved, review_queue, errors]) == len(input_strand_sets)`.

**BackendConfigurationError is a run-level failure.** When any weaver raises `BackendConfigurationError`, the executor raises it immediately from `execute()`, aborting the entire run.

**ReviewPolicy** controls what the executor does when `status=OK` and `requires_review=True`:
- `HALT` (default) — stop the chain, add to `review_queue` with remaining steps.
- `ALLOW_CONTINUE` — merge strands and continue. The entity will land in `resolved` if the rest of the braid succeeds.
- `RAISE` — raise `ReviewRequired` immediately.

**`AMBIGUOUS` always halts or raises — `ALLOW_CONTINUE` does not apply to it.** When `status=AMBIGUOUS`, `strands` is empty; there is nothing to merge. Continuing would silently do nothing, or worse, imply a candidate was chosen when it was not. The rule: `AMBIGUOUS` goes to `review_queue` (with `HALT`) or raises (with `RAISE`). `ALLOW_CONTINUE` is ignored for `AMBIGUOUS`. This is not configurable.

**`WeaveStatus.ERROR` policy (`ErrorPolicy`)** controls what happens after all fallback backends are exhausted or when no fallback is configured:
- `RECORD_AND_CONTINUE` (default) — add `ExecutionError` to `errors`, remove entity from active set, continue batch.
- `RAISE` — raise immediately, aborting execution. No `ExecutionResult` is returned; the entity is not added to `errors`.

To trigger backend fallback on `WeaveStatus.ERROR` before `ErrorPolicy` is applied, put `FallbackCondition.ERROR` in the `CapabilityInvocation.fallback_on` set.

**`confidence_threshold`** is an independent check. If any produced strand has `confidence < threshold`, the entity is halted by the same halt/continue/raise behaviour as `ReviewPolicy`. Both checks run independently; either can halt an entity.

### Preflight Validation and Per-step Guard

**Preflight — Missing inputs (runs once before any steps):** for each entity, check `braid.from_types ⊆ entity.available_types()`. Any entity that fails this check goes to `errors` with `MissingInputError` before execution begins. This handles the common case of heterogeneous batches where some entities lack the required starting strand types. Running this once upfront is simpler and cheaper than checking at every step.

**Guard 1 — Already satisfied (runs per step):** if an entity's `StrandSet` already contains all types in `step.output_types`, skip this step for that entity. No weaver call, no cache lookup. This handles entities that arrive with strands already populated from prior runs or from a different source.

No per-step Guard 2 is needed. Entities removed mid-execution (via `unresolved`, `review_queue`, or `errors`) are no longer in the active set, so subsequent steps never see them. A mid-step missing-input situation that isn't covered by the preflight check indicates a weaver contract violation (OK status but output types missing), which should surface as a test failure, not a runtime guard.

### Execution Flow (per step, per chunk)

1. Apply Guard 1: already-satisfied entities pass through unchanged.
2. Split remaining active entities into cache hits and misses using the superset validity rule.
3. For cache hits: treat the cached `WeaveResult` exactly like a fresh result — run it through steps 5–14 below with no weaver call. A cached `NO_MATCH` still goes to `unresolved`; a cached `AMBIGUOUS` still goes to `review_queue`.
4. For misses: split into sub-batches of at most `capability.max_batch_size` (if set). Call `weaver.execute_batch(...)` per sub-batch. Reassemble in original order.
5. On `BackendConfigurationError`: raise from `execute()` immediately, aborting the run.
6. On `BackendUnavailable`: this is a backend-level failure — retry the **entire** miss batch on the next fallback backend. Repeat until exhausted. If all backends exhausted, add all remaining entities to `errors`.
7. On `WeaveStatus.NO_MATCH` or `WeaveStatus.ERROR` with qualifying `fallback_on`: retry **only the affected entities** on the next fallback backend. Entities with `OK`, `AMBIGUOUS`, or other statuses keep their current-backend results and are not re-resolved.
8. On `WeaveStatus.NO_MATCH` with no remaining fallbacks: move entity to `unresolved`.
9. On `WeaveStatus.ERROR` with no remaining fallbacks: apply `ErrorPolicy` (`RECORD_AND_CONTINUE` → add `ExecutionError` to `errors`; `RAISE` → raise immediately).
10. On `WeaveStatus.AMBIGUOUS`: move to `review_queue` with remaining steps. If `ReviewPolicy.RAISE`, raise instead.
11. On `WeaveStatus.OK` with `requires_review=True`: apply `ReviewPolicy` (`HALT` → `review_queue`; `ALLOW_CONTINUE` → merge and continue; `RAISE` → raise).
12. On `confidence < threshold` for any OK result: apply `ReviewPolicy` identically to step 11.
13. Store result in cache via `put(base_key, result)`. Merge strands into `StrandSet`.
14. If this was the last step and the entity is still active: move to `resolved`.

**Chunked execution:** processes input in chunks (default 10,000). Each chunk passes through all braid steps before the next chunk starts.

The `LocalExecutor` runs in-process with asyncio. Synchronous weaver internals use `asyncio.to_thread()`.

---

## How TaxonWeaver Fits

TaxonWeaver becomes `NCBITaxonWeaver`, a `BaseWeaver` subclass. The existing `TaxonomyResolverService` is completely unchanged — the weaver is a thin async boundary around it.

### Manifest

```
Capability: ncbi.resolve_name
  consumes: {organism.name}
  produces: {ncbi.taxon.id, organism.scientific_name, ncbi.taxon.rank,
              ncbi.taxon.parent_id, ncbi.taxon.lineage,
              ncbi.taxon.match_type, ncbi.taxon.review_required}
  output_groups:
    id="core"
      ncbi.taxon.id, organism.scientific_name, ncbi.taxon.rank,
      ncbi.taxon.parent_id, ncbi.taxon.match_type, ncbi.taxon.review_required
      — single DB row fetch (taxon_names JOIN taxa)
    id="lineage"
      ncbi.taxon.lineage
      — separate lineage_cache lookup; weaver internally runs core first
  backends: (local,)

Capability: ncbi.resolve_taxid
  consumes: {ncbi.taxon.id}
  produces: {organism.scientific_name, organism.name, ncbi.taxon.rank,
              ncbi.taxon.parent_id, ncbi.taxon.lineage}
  output_groups:
    id="core"
      organism.scientific_name, organism.name, ncbi.taxon.rank, ncbi.taxon.parent_id
    id="lineage"
      ncbi.taxon.lineage
  backends: (local,)
```

### backend_fingerprint

`backend_fingerprint("local")` returns the `taxonomy_build_version` from `get_taxonomy_build_info()` (already in the database metadata table). `backend_fingerprint("api")` returns the Datasets v2 service identifier (e.g. `"datasets-v2"` / `"live"`). Each backend strategy supplies its own fingerprint; the weaver delegates to the selected backend.

### Backend strategies and dispatch

`NCBITaxonWeaver` holds a `dict[str, ResolutionBackend]` (`"local"` → `LocalTaxonomyBackend`, `"api"` → `DatasetsV2Backend`). `execute_batch` selects the strategy by the `backend` argument, raises `BackendUnavailable` if that strategy is absent or `is_configured()` is false, calls the strategy to produce a list of neutral `TaxonMatch` objects (in input order; the API path uses `_reorder_by_key`), then runs the single `TaxonMatch -> WeaveResult` mapper so both backends emit identical strand shapes. `ResolutionBackend` is the taxon-package interface; it implements core's generic `BackendStrategy` (which declares only `name`, `is_configured()`, and `fingerprint()` — no resolution-specific methods, so core stays domain-neutral).

### Connection handling

Uses `threading.local()` for one `TaxonomyResolverService` instance per thread. `asyncio.to_thread()` distributes calls across a thread pool; each thread gets its own SQLite connection, opened lazily on first use. The async `DatasetsV2Backend` needs no thread pool — it awaits an async HTTP client directly.

### execute_batch

For `ncbi.resolve_name` with `backend="local"`, calls `resolve_batch()` once with all names in the batch. Results come back in input order. Each `ResolveResult` maps to one `WeaveResult` with `computed_groups` accurately reflecting which groups were computed. If only the core group was requested, `computed_groups={"core"}`. If lineage was requested, the weaver ran both internally and reports `computed_groups={"core","lineage"}`.

### Construction and registration

`db_path` is required at construction for the `local` backend — omitting it is a `TypeError`. The `api` backend (NCBI Datasets v2) is configured separately; when a backend is selected at runtime but not configured in this instance, the weaver raises `BackendUnavailable`, which can trigger fallback to the other backend if `FallbackCondition.BACKEND_UNAVAILABLE` is in `fallback_on`.

```python
registry = BraidRegistry()
registry.register(NCBITaxonWeaver(db_path=Path(os.environ["TAXONOMY_DB_PATH"])))
```

`BackendConfigurationError` is raised at construction if `db_path` points to a non-existent file or cannot be opened as a SQLite database.

Entry-point declaration in `pyproject.toml` is deferred until the plugin-configuration mechanism is resolved.

---

## Package Structure

```
braidworks-core/
  braidworks/
    core/
      strand.py           Strand, StrandSet, MergePolicy
      capability.py       OutputGroup, Capability, WeaverManifest
      result.py           WeaveResult, WeaveStatus, CandidateResult
      weaver.py           BaseWeaver ABC
      braid.py            CapabilityInvocation, Braid, BackendPolicy,
                          FallbackCondition
      cache.py            StrandCacheKey, compute_cache_key, StrandCache protocol,
                          InMemoryStrandCache
      registry.py         BraidRegistry
      planner.py          Braider
      executor.py         LocalExecutor, ReviewPolicy, ErrorPolicy,
                          ExecutionResult, ExecutionError, ReviewQueueItem
      exceptions.py       BackendConfigurationError, BackendUnavailable,
                          NoPathError, NoPlanError, UnsupportedCapability,
                          ReviewRequired, MissingInputError, InvalidManifestError

taxonweaver/                              current taxonbridge, renamed
  taxonweaver/
    weaver.py             NCBITaxonWeaver  ← new
    service.py            TaxonomyResolverService  ← unchanged
    ...existing modules unchanged...
  pyproject.toml
    (entry-point declaration deferred; manual registration is the MVP path)

(future)
braidworks-celery/        CeleryExecutor — same Braid + ExecutionResult interface
```

---

## What is Explicitly Deferred

| Item | What keeps the door open |
|---|---|
| Multi-input capability planning | Capabilities declared in manifest; not projected in MVP graph; future braider activates them |
| Set-based braider | `Braider.plan()` takes `frozenset[str]`; braider internals are swappable; `Braid` interface unchanged |
| Celery executor | `Braid` and `ExecutionResult` are fully serializable |
| HPC executor | `StrandSet.to_json/from_json` exists; braid serialization exists; SQLite-on-NFS documented constraint |
| Redis cache | `StrandCache` is a Protocol; `get(key, requested_groups)` interface works for Redis with key-set indexing |
| Entry-point discovery | `register()` is already the interface; `discover()` can populate it once plugin configuration is resolved |
| TTL enforcement | Not in MVP interface; add `put(key, result, ttl)` when Redis is implemented |
| Calibrated confidence | `strand.metadata["calibrated_probability"]` when a weaver has real calibration data |
| Parallel step execution | Topological sort identifies independent steps; parallelism is an executor feature |
| Type schema versioning | Type IDs are the extension point; version suffix when needed |
| `BackendPolicy.ANY` | Requires per-backend cost model; add when `backend_costs: dict[str, float]` is added to `Capability` |

---

## Key Invariants

These must hold throughout the implementation and must be covered by tests:

1. **One result per input, in order.** `execute_batch` always returns `len(strand_sets)` results in input order.
2. **Cache fingerprint uses only consumed types, no provenance.** Same value, different upstream path = same cache entry. Extra strands in the StrandSet do not affect the fingerprint.
3. **Cache key contains no group information.** `requested_groups` is passed to `get()` separately; it is never part of the key.
4. **Cache validity requires group superset.** A cached entry is only a hit when `cached_result.computed_groups ⊇ triggered_groups(requested_outputs)`.
5. **`backend_fingerprint` in cache key, evaluated per-backend.** Upgrading a local database invalidates old entries without any manual flush; a result is cached under the fingerprint of the backend that produced it (`result.backend_used`), never a backend-blind value.
6. **`BackendConfigurationError` aborts the run.** Never per-entity, never triggers fallback.
7. **Braider intersects BackendPolicy with capability.backends.** A backend not in `capability.backends` is never assigned. Impossible combinations raise `NoPlanError` at plan time.
8. **`Capability.backends` only declares backends implemented by the weaver class.** Declaring a backend with no implementation is a manifest lie and will be rejected by validation. `BackendUnavailable` is valid only when an implemented backend is unavailable in this configured instance (e.g. a multi-backend weaver class instantiated without a specific backend's credentials).
9. **`Braid.from_types` is the minimal required starting set.** Computed as `union(input_types) - union(output_types)` across all steps. Not equal to the full `available_types` passed to the braider.
10. **Executor respects `max_batch_size`.** Miss lists are split into sub-batches before calling `execute_batch`. The weaver never receives more items than `max_batch_size`.
11. **Per-entity fallback is per-entity.** `NO_MATCH`/`ERROR` fallback retries only affected entities. `BackendUnavailable` retries the whole batch on the next backend.
12. **Preflight validates starting inputs before any steps run.** Entities missing `braid.from_types` go to `errors` immediately.
13. **Guard 1 runs per-step before cache split.** Already-satisfied entities skip steps without weaver calls.
14. **`AMBIGUOUS` always halts or raises.** `ALLOW_CONTINUE` is never applied to an `AMBIGUOUS` result.
15. **`NO_MATCH` goes to `unresolved`, not `errors` or `resolved`.** It is a valid data outcome, not a failure.
16. **`ErrorPolicy.RAISE` aborts execution; no `ExecutionResult` is returned.** The entity is not added to `errors`.
17. **`ExecutionError` is JSON-serializable.** No raw `Exception` objects in `ExecutionResult`.
18. **`backend_fingerprint(backend)` is abstract.** No weaver may accidentally inherit `"unknown"`; it is evaluated per-backend.
19. **Manifest validation runs at `register()` time.** Invalid manifests raise `InvalidManifestError` before any graph is built.
20. **Weaver computes only triggered output groups externally.** It may compute more internally (reported via `computed_groups`); it must not skip externally triggered groups.
21. **`requires_review=True` halts by default.** Executor does not silently continue through a review gate.
22. **`confidence` and `requires_review` are independent.**
23. **`ReviewQueueItem` includes `remaining_steps`.** Halted entities carry what is needed to resume after human review.
24. **Multi-input capabilities are not in the MVP graph.**
25. **Collection types use plural type IDs.**
