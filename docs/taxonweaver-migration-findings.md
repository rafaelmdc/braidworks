# taxonweaver → weaverkit migration: findings log (TEMPORARY)

Running index of problems, edge-cases, and gaps found while reshaping the
hand-written `taxonweaver` onto the `weaverkit` backbone by following the
Spec → Scaffold → Implement → Verify guide. Each entry is a candidate weaverkit
fix/ticket. **This file is scratch** — we triage and delete it once the items are
either fixed in weaverkit or filed as real issues.

Status legend: 🔴 blocker · 🟠 friction · 🟡 papercut · 🔵 observation

Each entry: what the guide/backbone assumes, what the real weaver needs, and a
proposed direction.

---

## A. 🔴 `computed_groups` cannot express "a group is always computed internally"

- **Backbone:** the generated resolver mapper sets
  `computed_groups = capability.triggered_groups(requested_outputs)`
  (`_MAPPER_RESOLVER`, scaffold.py).
- **Real weaver:** `taxonweaver/mapper.py:64` does
  `computed_groups = frozenset(triggered | {"core"})` — the resolver *always*
  resolves the name to a taxid (the `core` group) even when the caller only asked
  for `lineage`. `computed_groups` feeds the cache key, so under-reporting it
  corrupts cache reasoning.
- **Why the generated mapper can't know this:** it's a domain fact (this source
  computes core unconditionally), not derivable from the spec as written.
- **Proposed direction:** add a per-capability spec field, e.g.
  `always_computed_groups = ["core"]`, that the generated mapper unions into
  `computed_groups`. Keeps the mapper generated (no hand-edit) and the fact
  declared in the spec. *(This is the one real backbone change anticipated in the
  task plan.)*

## B. 🟠 Backend only receives `requested_outputs`, not the triggered-group semantics

- **Backbone:** the generated dispatch calls
  `fetch(capability_id, queries, requested_outputs=requested_outputs)`. The
  "empty requested_outputs == all groups" semantics live in
  `Capability.triggered_groups`, which the backend doesn't have.
- **Real weaver:** the old dispatch computed
  `need_lineage = "lineage" in cap.triggered_groups(requested_outputs)` and passed
  a clean bool to `resolve(...)`. Lineage is the expensive path, so the backend
  must know whether to do it — and must replicate the empty-means-all rule to do so
  correctly from `requested_outputs` alone.
- **Proposed direction:** either (1) have the dispatch also pass the resolved
  `triggered_groups` (or the `Capability`) to `fetch`, or (2) document a tiny
  helper the backend uses, e.g. `needs_group(requested_outputs, "lineage", cap)`.
  Option (1) is cleaner and keeps "empty == all" in one place.

## C. 🟠 Generated `build_<package>()` takes no args, but a real weaver needs configuration

- **Backbone:** `weaverkit verify` imports `<package>.factory.build_<package>` and
  calls it **with no arguments**; the generated factory wires backends with no
  config.
- **Real weaver:** `build_ncbi_weaver(...)` has many knobs (`db_path`,
  `enable_api`, `api_key`, injected `httpx` client, `allow_fuzzy`, consent prompt)
  and **raises `BackendConfigurationError` if nothing is configured** — so a
  no-arg call fails by design (no backend → no weaver).
- **Tension:** verify needs a zero-config constructor; a multi-backend weaver
  needs configuration and a "at least one backend" guard.
- **Proposed direction:** let the spec/scaffold generate a `build_<package>()` that
  returns a *manifest-complete but possibly all-unconfigured* weaver (backends
  present but `is_configured()==False`), so verify can inspect the manifest and
  fingerprints without real data. Keep the rich, raising `build_*` as a separate
  configured entry point. Clarify in the guide which one verify targets.

## D. 🟠 Builder/identity naming: `weaver_id` ≠ package, builder name fixed to package

- **Backbone:** verify calls `build_{package}` → `build_taxonweaver`; provider/
  mapper use `WEAVER_ID`.
- **Real weaver:** package is `taxonweaver`, but `weaver_id` is `"ncbi"` and the
  builder is `build_ncbi_weaver`. The spec supports `weaver_id != db_name`
  (good), but the *builder function name* is hard-wired to the package by verify.
- **Proposed direction:** either accept `build_<weaver_id>` as an alternative, or
  document that the builder must be named `build_<package>` and provide an alias.
  Decide and note in the guide.

## E. 🟠 `verify --strict` is unreachable for a multi-GB-DB-only weaver

- **Backbone:** `--strict` (definition-of-done) requires golden examples to
  actually run on `spec.backends[0]`.
- **Real weaver:** the verifiable data lives in a ~1.2 GB local SQLite built from a
  ~70 MB download, or behind the live API. Neither is available in a plain
  `verify`/CI run, so golden **skips** — and `--strict` then fails for lack of a
  runnable golden.
- **Proposed direction:** `--strict` should treat "golden skipped because the only
  backends need external data" as a distinct, non-failing (or explicitly opt-in)
  state — e.g. `--strict` passes if golden ran *or* was legitimately skipped, with
  a separate `--strict-golden` to demand execution. Otherwise big-DB weavers can
  never be "done."

## F. 🔵 Produced type_ids that aren't registered shared keys are invisible to the index

- `ncbi.taxon.parent_id`, `ncbi.taxon.match_type`, `ncbi.taxon.review_required` are
  produced but not in `SHARED_KEYS` (only `consumes` must be registered). That's
  allowed, but the index's reachability can't see them as potential join targets.
- **Observation only:** these are leaf/descriptive outputs, not join keys, so this
  is probably fine. Flagging in case we later want produced join keys registered.

## G. 🔵 Resolver record forces typed domain fields through an untyped `values` dict

- **Backbone:** the generated `*Record` carries `values: dict[str, Any]` keyed by
  produced type_id; the mapper iterates it.
- **Real weaver:** `TaxonMatch` has typed fields (`taxid`, `scientific_name`,
  `rank`, `parent_taxid`, `lineage`, …). Migrating means the backend flattens these
  into `values` (e.g. `values[TAXON_ID] = taxid`), and the `review_required` output
  is both a record flag *and* a `values` entry (slight duplication).
- **Observation:** workable; the loss of per-field typing in the intermediate is
  the cost of the generic mapper. Note for ergonomics.

## H. 🔴 Local backend validates-in-`__init__` / `is_configured()` always True (inverse of backbone)

- **Backbone:** a backend constructs cheaply and never raises for missing data;
  `is_configured()` returns whether the data is actually present; the dispatch gates
  on it (raises `BackendUnavailable` upstream, golden skips). This lets verify build
  a manifest-complete weaver with *unconfigured* backends and introspect it.
- **Real weaver:** `LocalTaxonomyBackend.__init__` raises
  `BackendConfigurationError` if the DB file is missing (local.py:52), and
  `is_configured()` **always returns True** once constructed (local.py:68). So you
  cannot construct it without the ~1.2 GB DB, and once you can, it never reports
  "unconfigured."
- **Impact:** blocks a zero-config `build_taxonweaver()` (Finding C) and inverts the
  skip-when-unconfigured contract the golden tests rely on.
- **Proposed direction:** migrate the backend to the backbone shape —
  `__init__` stores the path and sets `self._configured = db_is_valid(path)`
  (no raise); `is_configured()` returns it. Move the hard "you asked for local but
  it's absent" error to the *configured* builder path, not construction.

## I. 🟠 `verify` crashes (uncaught `AttributeError`) when the builder isn't `build_<package>`

- **Backbone:** `_build_weaver` does `getattr(module, f"build_{package}")` and only
  catches `ModuleNotFoundError`. A package whose builder is named differently
  (here `build_ncbi_weaver`) makes verify **traceback**, not emit a clean problem.
- **Proposed direction:** catch `AttributeError` and report a fix-oriented finding
  ("expected `build_<package>(...)`; found none — rename or add an alias"). Cheap,
  and pairs with the Finding D naming decision.

---

## Migration progress

- [x] Read existing taxonweaver contract (vocab/intermediate/mapper/dispatch/
      backends/factory/provider/setup).
- [x] Write `taxonweaver/weaver.spec.toml` (resolver, 2 caps, [bulk], golden) —
      spec validates clean (verify got past validation to the build step).
- [~] `weaverkit verify` the spec against the existing package; log mismatches —
      surfaced findings C/D/H/I before manifest comparison could even run.
- [ ] Reconcile manifest/dispatch/mapper onto the backbone.
- [ ] Reconcile backends (local/api) to the `fetch` contract.
- [ ] Green `weaverkit verify` (non-strict) + package test suite.
