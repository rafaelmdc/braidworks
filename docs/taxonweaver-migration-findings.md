# taxonweaver → weaverkit migration: findings log (TEMPORARY)

Running index of problems, edge-cases, and gaps found while reshaping the
hand-written `taxonweaver` onto the `weaverkit` backbone by following the
Spec → Scaffold → Implement → Verify guide. Each entry is a candidate weaverkit
fix/ticket. **This file is scratch** — we triage and delete it once the items are
either fixed in weaverkit or filed as real issues.

Status legend: 🔴 blocker · 🟠 friction · 🟡 papercut · 🔵 observation

Each entry: what the guide/backbone assumes, what the real weaver needs, and a
proposed direction.

## ⏸ Decision needed before the build can continue (see J)

The blocking realization: taxonweaver already has a **deliberate, test-locked
contract that conflicts with the backbone's** (no-arg build raises; local backend
raises on a missing DB and is always "configured" once built). Migrating is not
"copy code over" — it's choosing one of:

1. **Adapt weaverkit** to the real weaver's shape (zero-config introspection
   builder *plus* a configured builder; `is_configured()` reflecting data; a
   conformance hook to build a tiny fixture DB). Findings A/C/H/I become weaverkit
   tickets. taxonweaver's existing tests mostly stand.
2. **Rewrite taxonweaver** (and ~15 tests) to the current backbone contract.
   Faster to a green `verify`, but throws away a working, well-tested contract and
   the rich configured builder.

Recommendation: **(1)** — the backbone is young and these gaps are real; the weaver
is the proven artifact. But this is the user's call; logged and paused here.

---

## A. ✅ FIXED — `computed_groups` cannot express "a group is always computed internally"

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
- **Resolution:** implemented. `CapabilitySpec.always_computed_groups` (validated
  against declared group ids); `vocab.py` emits `ALWAYS_COMPUTED_GROUPS`; both
  generated mappers union it into `computed_groups`. Documented in
  implementing-backends.md. The taxonweaver spec now sets
  `always_computed_groups = ["core"]` on both capabilities, matching the old
  `triggered | {"core"}`.

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

## C. ✅ FIXED — Generated `build_<package>()` takes no args, but a real weaver needs configuration

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
- **Resolution:** added `build_taxonweaver()` (zero-config introspection builder:
  wires the local backend present-but-unconfigured + the public API backend) as
  the name verify calls; `build_ncbi_weaver(...)` stays the rich configured
  builder. **Two-builder convention** = `build_<package>()` for introspection,
  a domain-named configured builder for real use. *(weaverkit TODO: scaffold this
  convention by default — the generated factory should emit a zero-config
  `build_<package>()` AND a config-taking builder, and the guide should name the
  convention.)*

## D. ✅ RESOLVED (convention) — Builder/identity naming: `weaver_id` ≠ package

- **Backbone:** verify calls `build_{package}` → `build_taxonweaver`; provider/
  mapper use `WEAVER_ID`.
- **Real weaver:** package is `taxonweaver`, but `weaver_id` is `"ncbi"` and the
  builder is `build_ncbi_weaver`. The spec supports `weaver_id != db_name`
  (good), but the *builder function name* is hard-wired to the package by verify.
- **Decision:** the introspection builder is named `build_<package>` (verify's
  target); `weaver_id` is free to differ (it's the join namespace, here `ncbi`).
  taxonweaver provides `build_taxonweaver()` (introspection) alongside
  `build_ncbi_weaver()` (configured). Codify in the guide.

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
- **Mitigation found:** taxonweaver's `tests/conftest.py::build_mini_db` builds a
  *tiny synthetic* taxonomy SQLite (a handful of `names.dmp`/`nodes.dmp` rows,
  inline) on the fly — golden/verify *can* run real resolutions with no 1.2 GB
  download. This is a reusable pattern: weaverkit conformance could accept a
  "build a fixture DB" hook so `--strict` runs golden against a fixture, not the
  full bulk source. Strongly softens E.

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

## H. ✅ FIXED — Local backend validates-in-`__init__` / `is_configured()` always True (inverse of backbone)

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
- **Test lock-in (turned out small):** only ONE test directly constructed
  `LocalTaxonomyBackend(missing)` expecting a raise. The factory-level actionable
  error (`build_ncbi_weaver(db_path=missing)`) is raised by `ensure_taxonomy_db`,
  not the backend, so those tests stood. Blast radius = 1 test, not ~15.
- **Resolution:** `__init__` now sets `self._configured = db_is_valid(path)` (no
  raise); `is_configured()` returns it. The one test now asserts the unconfigured
  construction instead of a raise. Pairs with Finding K (fingerprint guard).

## I. 🟠 `verify` crashes (uncaught `AttributeError`) when the builder isn't `build_<package>`

- **Backbone:** `_build_weaver` does `getattr(module, f"build_{package}")` and only
  catches `ModuleNotFoundError`. A package whose builder is named differently
  (here `build_ncbi_weaver`) makes verify **traceback**, not emit a clean problem.
- **Proposed direction:** catch `AttributeError` and report a fix-oriented finding
  ("expected `build_<package>(...)`; found none — rename or add an alias"). Cheap,
  and pairs with the Finding D naming decision.

## K. ✅ FIXED — `backend_fingerprint` calls `fingerprint()` on unconfigured backends

- **Backbone:** the dispatch's `backend_fingerprint` returned `strat.fingerprint()`
  for any present backend, guarding only the `strat is None` case.
- **Real weaver:** taxonweaver's local `fingerprint()` reads the DB (its build
  version). With the zero-config builder wiring an *unconfigured* local backend
  (Findings C/H), `backend_fingerprint("local")` would try to read a DB that isn't
  there. Generated stubs hid this because their `fingerprint()` returns a static
  string.
- **Resolution:** `backend_fingerprint` now returns `f"unconfigured:{backend}"`
  unless `strat.is_configured()`. Fixed in `taxonweaver/dispatch.py` *and* the
  scaffold `_DISPATCH` template, so every future weaver inherits the guard.

## B/G. 🔵 Reframed: optional "full-adoption" items, not blockers

taxonweaver **conforms to the spec while keeping its own richer, better-typed
internals** (its `TaxonMatch`/mapper/dispatch with `resolve(need_lineage=...)`),
because `verify` checks the *manifest + fingerprints + golden*, not that the
package uses the generated `intermediate.py`/`mapper.py`/`dispatch.py` verbatim.
So:

- **B** (derive `need_lineage` from `requested_outputs`) and **G** (flatten
  `TaxonMatch` into `values`) only matter if a weaver adopts the *generated*
  dispatch/mapper. They're real ergonomics notes for that path, but **not required
  to conform** — taxonweaver is proof a weaver can keep hand-tuned internals.
- Open weaverkit question: is "conform via the manifest, bring your own plumbing" a
  blessed pattern, or should the guide nudge toward the generated files? Document
  the stance either way.

## J. 🔴→🟢 The central fork: backbone contract vs. taxonweaver's test-locked contract

This is the meta-finding the others roll up into. The backbone assumes a weaver
that (a) constructs zero-config, (b) reports configured/unconfigured via
`is_configured()`, (c) has a `build_<package>()` introspection entry point, and
(d) can run golden against available data. taxonweaver instead has a rich,
*configuration-required* contract that **raises** when unconfigured and is locked
in by ~15 passing tests. Neither side is wrong — the weaver predates the backbone.

The migration therefore can't proceed as a mechanical "scaffold + copy" without
first deciding direction (see the ⏸ box up top). The proposed split is:

- **weaverkit changes** (Findings A, C, E, I; D as a doc decision): always-computed
  groups in the spec; a two-builder convention (introspection vs configured);
  fixture-DB conformance hook; graceful `AttributeError` handling. These are the
  real product of this exercise.
- **taxonweaver changes** (Findings H, G; B at the dispatch): backbone-shaped
  backend construction, flatten `TaxonMatch` into `values`, derive `need_lineage`
  from `requested_outputs`. Plus a rewrite of the ~15 contract tests.

Until (1) vs (2) is chosen, the build is paused here intentionally — going further
would either silently rewrite the backbone or break the suite.

---

## Migration progress

- [x] Read existing taxonweaver contract (vocab/intermediate/mapper/dispatch/
      backends/factory/provider/setup).
- [x] Write `taxonweaver/weaver.spec.toml` (resolver, 2 caps, [bulk], golden) —
      validates clean, now declares `always_computed_groups = ["core"]`.
- [x] `weaverkit verify` the spec against the existing package; log mismatches —
      surfaced findings C/D/H/I before manifest comparison could run.
- [x] **Decision (J): adapt weaverkit** (user, 2026-06-08).
- [x] Fix Finding I (verify reports a misnamed builder, no crash). ✅
- [x] Fix Finding A (`always_computed_groups` → mapper `computed_groups`). ✅
- [x] Fix Finding C/D: `build_taxonweaver()` zero-config introspection builder +
      two-builder convention. ✅
- [x] Fix Finding H: backbone-shaped backend construction (1 test changed, not 15). ✅
- [x] Fix Finding K: `backend_fingerprint` guards `is_configured()`. ✅
- [x] **Green `weaverkit verify` (non-strict)** + full suite green. ✅✅
- [ ] (weaverkit, deferred) Finding E: fixture-DB conformance hook so `--strict`
      can run golden against a tiny built DB (use `build_mini_db`).
- [ ] (weaverkit, deferred) Scaffold the two-builder convention by default; bless
      (or discourage) "conform via manifest, bring your own plumbing" (B/G).
- [ ] (optional) Adopt generated dispatch/mapper/intermediate verbatim (B/G) — not
      required to conform.

### Where the build stands now

Branch `taxonweaver-weaverkit-migration`. **taxonweaver conforms to its weaverkit
spec** — `weaverkit verify` is green (spec valid, manifest matches, fingerprints
OK, reachable). Full workspace green: core 96, taxonweaver 92 + 8 skipped,
weaverkit 95. The remaining items are weaverkit-side enhancements (E + scaffolding
the conventions) and an optional verbatim-plumbing adoption — none block the
migration's goal, which is met.

### Net result of the exercise

Driving the migration surfaced and fixed **5 real backbone gaps** (A, C, I, K, +
the H/D contract clarification) plus the two-builder convention — exactly the
"double whammy" intended. Remaining weaverkit tickets (E, scaffold the
conventions, B/G stance) are filed above; this scratch file can be deleted once
they're moved into real issues.
