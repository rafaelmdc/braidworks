# weaverkit backlog

Concrete work derived from `decisions.md`, prioritized. Each ticket names the
decision it implements, the change, and how we'll know it's done. These replace the
(now-deleted) ncbi_weaver migration scratch log.

Status: the ncbi_weaver migration goal is **met** — it conforms to its spec and
`weaverkit verify` (non-strict) is green. Everything below is backbone hardening.

---

## P1 — `--strict` fixture hook + formal regimes (Decision E) — ✅ DONE

**Why first:** it's the only item that changes what "done" *means*, and it unblocks
`verify --strict` for every real (big-dataset) weaver. Highest leverage.

**Shipped:** `verify --strict` now runs golden against `build_<package>_fixture()`
when present, else an already-configured backend on `build_<package>()`, else fails
with an actionable message (skip ≠ pass). `ncbi_weaver` ships
`build_ncbi_weaver_fixture()` (mini *Faecalibacterium* SQLite from inline dumps in
`weavers/ncbi_weaver/src/ncbi_weaver/fixture.py`, single source shared with the tests) and **passes
`verify --strict` with no 1.2 GB build**. `example_weaver` stays green via the
bundled-data fallback. Documented in implementing-backends.md.

- Add a fixture mechanism the conformance harness can call to build/point at a tiny
  deterministic dataset, generalizing ncbi_weaver's `tests/conftest.py::build_mini_db`.
  Likely shape: an optional, conventionally-named hook (e.g. a `build_fixture()` in
  the weaver, or a `[fixture]` section in the spec) that returns a configured weaver
  for golden.
- Redefine `verify --strict`: golden must **run against the fixture**; "skipped, no
  data" becomes an **invalid** state under `--strict` (clear, fix-oriented error:
  "provide a fixture so golden can run"). Plain `verify` keeps skip-is-ok.
- Keep live/E2E strictly opt-in and out of `--strict`.
- **Done when:** ncbi_weaver passes `verify --strict` in CI with *no* 1.2 GB
  download, golden running against the mini fixture; a weaver with no fixture fails
  `--strict` with the actionable message.

## P2 — Dispatcher pre-resolves `groups_to_compute` (Decision B) — ✅ DONE

**Shipped:** `fetch` now takes `groups_to_compute: frozenset[str]` — the dispatch
computes `cap.triggered_groups(requested_outputs)` and passes it; backends gate
expensive paths on membership (`"lineage" in groups_to_compute`) instead of
re-deriving group semantics. Updated across the generated templates (dispatch,
base, 3 stubs, fetch-hints) and example_weaver (dispatch + base + local). Note: the
earlier "empty means all" worry was a red herring — `triggered_groups` returns
groups whose outputs intersect the request, no implicit expansion. **ncbi_weaver
already complied** (its own dispatch pre-resolves `need_lineage` and passes it to
`resolve()`), so it needed no change — a nice confirmation of the principle. +1
behavioral weaverkit test. Documented in implementing-backends.md.

### original notes

- Dispatcher computes the normalized triggered-group set (empty = all expanded) and
  passes `groups_to_compute: frozenset[str]` to `fetch` alongside `requested_outputs`.
- Update the generated `_DISPATCH` template, the `fetch` signature + contract in
  `implementing-backends.md`, and the fetch-hint stubs. Backends key expensive-path
  decisions off `groups_to_compute`, never re-derive "empty = all".
- Migrate ncbi_weaver's backend to take `groups_to_compute` (drop the local
  `need_lineage = "lineage" in cap.triggered_groups(...)` derivation in dispatch;
  it moves to the dispatcher as the resolved set).
- **Done when:** a backend never imports/re-implements `triggered_groups`; generated
  + ncbi_weaver backends use the resolved set; tests cover empty-means-all.

## P3 — Scaffold the two-builder convention by default (Decisions C/D) — ✅ DONE

**Shipped:** the generated `factory.py` now documents the convention and ships
`build_<package>()` as the explicit zero-config *introspection* builder, plus
commented skeletons for a *configured* builder and an optional
`build_<package>_fixture()`. Documented in implementing-backends.md ("Builders")
and AGENTS.md (the Implement step).

### original notes

- The generated `_FACTORY` should emit **both** a zero-config `build_<package>()`
  (introspection: backends present, possibly unconfigured) **and** a config-taking
  builder. Today it emits only one `build_<package>(**config)`.
- Name the convention in `AGENTS.md` + the guide so weaver authors don't hand-roll
  it (ncbi_weaver had to: `build_ncbi_weaver` + `build_ncbi_weaver`).
- **Done when:** a freshly scaffolded weaver has both builders and `verify` targets
  the introspection one with no extra work.

## P4 — Document "thin contract, free implementation" (Decisions B/G) — ✅ DONE

**Shipped:** implementing-backends.md now has an "Advanced: conform with your own
plumbing" section blessing both patterns — (1) bring your own
dispatch/mapper/intermediate (ncbi_weaver as the worked example), and (2) typed
domain record projected to `values` at the mapper seam — and states the generated
files are the default, not a requirement.

### original notes

- In the guide / `PITFALLS.md`: bless two patterns explicitly —
  (1) "conform via the manifest, bring your own dispatch/mapper/intermediate"
  (ncbi_weaver is the worked example), and
  (2) "typed domain record → project to `values` at the mapper seam."
- State that the generated `values`-dict record + generated mapper are the *default*
  for simple weavers, not a requirement.
- **Done when:** the docs name both patterns and point at ncbi_weaver as the
  advanced reference.

## P5 — Output-name catalog (Decision F) — ✅ DONE

**Shipped:** `weaverkit.keys.OUTPUT_KEYS` catalogs produced *leaf/payload* outputs
(non-join fields) with `is_known_output()` (= shared key or catalogued). `weaverkit
index` prints an **advisory** (non-failing) listing produced fields in neither
registry, so descriptive names don't drift (`parent_id` vs `parent_taxon_id`).
Catalog seeded with the current weavers' leaf outputs; not registry membership —
promote to `SHARED_KEYS` to make a field join-eligible.

---

## Pre-existing / separate

- **#7 — ✅ DONE (un-deferred).** Extracted the generic local-DB plumbing into
  `braidworks.core.localdb` (`ensure_local_db` + `default_db_path` / `auto_consented`
  / `download` / `md5_file` / `fetch_remote_md5` / `check_disk` / `BuildLock`). It's
  **callback-shaped** (caller supplies `is_valid` + `build` + consent message), so
  it carries no taxonomy assumptions — mitigating the rule-of-three risk. ncbi_weaver's
  `setup.py` now delegates to it (keeping only taxdump specifics), and the scaffold's
  bulk `setup.py` template delegates too, so future bulk weavers get the plumbing
  free. +12 core tests.
- ncbi_weaver optional: adopt the generated dispatch/mapper/intermediate verbatim
  (only if we decide rich weavers should converge on generated plumbing — currently
  P4 says no, they needn't).
