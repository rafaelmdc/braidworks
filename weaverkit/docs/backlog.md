# weaverkit backlog

Concrete work derived from `decisions.md`, prioritized. Each ticket names the
decision it implements, the change, and how we'll know it's done. These replace the
(now-deleted) taxonweaver migration scratch log.

Status: the taxonweaver migration goal is **met** — it conforms to its spec and
`weaverkit verify` (non-strict) is green. Everything below is backbone hardening.

---

## P1 — `--strict` fixture hook + formal regimes (Decision E) — ✅ DONE

**Why first:** it's the only item that changes what "done" *means*, and it unblocks
`verify --strict` for every real (big-dataset) weaver. Highest leverage.

**Shipped:** `verify --strict` now runs golden against `build_<package>_fixture()`
when present, else an already-configured backend on `build_<package>()`, else fails
with an actionable message (skip ≠ pass). `taxonweaver` ships
`build_taxonweaver_fixture()` (mini *Faecalibacterium* SQLite from inline dumps in
`taxonweaver/fixture.py`, single source shared with the tests) and **passes
`verify --strict` with no 1.2 GB build**. `exampleweaver` stays green via the
bundled-data fallback. Documented in implementing-backends.md.

- Add a fixture mechanism the conformance harness can call to build/point at a tiny
  deterministic dataset, generalizing taxonweaver's `tests/conftest.py::build_mini_db`.
  Likely shape: an optional, conventionally-named hook (e.g. a `build_fixture()` in
  the weaver, or a `[fixture]` section in the spec) that returns a configured weaver
  for golden.
- Redefine `verify --strict`: golden must **run against the fixture**; "skipped, no
  data" becomes an **invalid** state under `--strict` (clear, fix-oriented error:
  "provide a fixture so golden can run"). Plain `verify` keeps skip-is-ok.
- Keep live/E2E strictly opt-in and out of `--strict`.
- **Done when:** taxonweaver passes `verify --strict` in CI with *no* 1.2 GB
  download, golden running against the mini fixture; a weaver with no fixture fails
  `--strict` with the actionable message.

## P2 — Dispatcher pre-resolves `groups_to_compute` (Decision B)

- Dispatcher computes the normalized triggered-group set (empty = all expanded) and
  passes `groups_to_compute: frozenset[str]` to `fetch` alongside `requested_outputs`.
- Update the generated `_DISPATCH` template, the `fetch` signature + contract in
  `implementing-backends.md`, and the fetch-hint stubs. Backends key expensive-path
  decisions off `groups_to_compute`, never re-derive "empty = all".
- Migrate taxonweaver's backend to take `groups_to_compute` (drop the local
  `need_lineage = "lineage" in cap.triggered_groups(...)` derivation in dispatch;
  it moves to the dispatcher as the resolved set).
- **Done when:** a backend never imports/re-implements `triggered_groups`; generated
  + taxonweaver backends use the resolved set; tests cover empty-means-all.

## P3 — Scaffold the two-builder convention by default (Decisions C/D)

- The generated `_FACTORY` should emit **both** a zero-config `build_<package>()`
  (introspection: backends present, possibly unconfigured) **and** a config-taking
  builder. Today it emits only one `build_<package>(**config)`.
- Name the convention in `AGENTS.md` + the guide so weaver authors don't hand-roll
  it (taxonweaver had to: `build_taxonweaver` + `build_ncbi_weaver`).
- **Done when:** a freshly scaffolded weaver has both builders and `verify` targets
  the introspection one with no extra work.

## P4 — Document "thin contract, free implementation" (Decisions B/G)

- In the guide / `PITFALLS.md`: bless two patterns explicitly —
  (1) "conform via the manifest, bring your own dispatch/mapper/intermediate"
  (taxonweaver is the worked example), and
  (2) "typed domain record → project to `values` at the mapper seam."
- State that the generated `values`-dict record + generated mapper are the *default*
  for simple weavers, not a requirement.
- **Done when:** the docs name both patterns and point at taxonweaver as the
  advanced reference.

## P5 (soft) — Output-name catalog (Decision F)

- Optional, low priority. A lightweight catalog of produced (non-shared) type_id
  names so descriptive outputs don't drift (`parent_id` vs `parent_taxon_id`).
  **Not** shared-key registry membership — visibility/naming only. Revisit when a
  second weaver emits overlapping descriptive fields.

---

## Pre-existing / separate

- **#7 (deferred)** — extract shared local-DB plumbing into `braidworks-core` (not
  weaverkit), seeded from taxonweaver's `setup.py`, once ≥2 real bulk weavers exist.
- taxonweaver optional: adopt the generated dispatch/mapper/intermediate verbatim
  (only if we decide rich weavers should converge on generated plumbing — currently
  P4 says no, they needn't).
