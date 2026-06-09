# bacdive_weaver build notes (temporary)

Running log of problems / struggles / rough edges hit while building
`bacdive_weaver` — the **first real weaver built from scratch** through the
weaverkit loop (taxon_weaver was a migration of pre-existing code). Captured as
we go so we can tackle them deliberately afterwards; fold the keepers into
`weaverkit/docs/PITFALLS.md` / the implementation guide and delete this file.

## Findings

### 1. Rename regex missed `<db>`-glued doc placeholders
The `<db>_weaver` rename (PR #11) used `s/([a-z])weaver/\1_weaver/`, which requires
a **lowercase letter** immediately before `weaver`. Doc placeholders like
`<db>weaver` / `<db_name>weaver` have `>` before `weaver`, so they survived in
AGENTS.md, the implementation guide, README, etc. Fixed here.
**Lesson:** a token rename needs to cover placeholder forms, not just real
identifiers — grep the bare `weaver` suffix after, not just `[a-z]weaver`.

### 2. Workspace glob breaks `uv` before the package exists
The root `pyproject.toml` has `members = [..., "weavers/*"]`. The moment you create
`weavers/bacdive_weaver/` to hold the spec, every `uv run …` fails with
*"Workspace member … is missing a pyproject.toml"* — so you can't even validate the
spec in place. The spec must live **outside** `weavers/` (e.g. `/tmp` or repo root)
until `make new-weaver` stamps a real package, then it gets copied in.
**Lesson:** the docs say `make new-weaver SPEC=path DEST=weavers/<db>_weaver` but
should explicitly warn: don't pre-create the DEST dir / don't keep the spec there
pre-scaffold. Consider having the scaffold tolerate a dir containing only the spec.

### 3. No type-strain filter → scan-and-short-circuit (mitigated by batching)
BacDive has no "type strains only" query and no species summary. To get the
representative we page the `taxon/{genus}/{species}` ID list and `fetch` records
until one has `type strain == "yes"`. The type strain can be deep in the list —
*E. coli*'s is ~500 strains in (BacDive id 4907, DSM 30083) out of ~1,884 — so a
naive **one-by-one** scan with the original default cap (200) **misses it
entirely**. Fixed by batch fetch (#4): chunks of 100 → ~5 calls to reach it; raised
the default cap to 1,000. NO_MATCH only if no type strain within the cap. Remaining
expansion: cache + aggregate fallback (CONTRIBUTING).
**Lesson:** test the flagship example end-to-end *live* early — the unit fixture
(type strain at position 2) hid that the real default cap was too low.

### 4. Multi-id `fetch` format is **semicolon**-joined (RESOLVED live)
`GET /fetch/24,4409` (comma) → 404; `GET /fetch/4409;4410;4907` (semicolon) → 200
with all three results. The docs say "≤100 ids" but don't show the separator.
Implemented batch fetch with `;`. **Lesson:** the API docs underspecify the batch
syntax; a live probe settled it — worth noting in the implementing-backends guide
that "≤N ids per call" needs the separator confirmed against the live service.

### 5. `requested_outputs` / group gating not used (deliberate)
The whole strain record arrives in one fetch, so computing all traits is free; the
shared `map_lookup` already filters to `outputs_to_compute`. So `fetch` returns
every produced trait and ignores `groups_to_compute` — gating would add nothing.
Worth a one-liner in the backend guide: gate only when a group costs an extra call.

### 6. Keyless always-on API defeats the "golden skips when unconfigured" escape
The generated conformance/contract tests assume a backend is *unconfigured* in CI
(no DB / no key), so golden + order tests **skip** unless data is present, and
`--strict` swaps in the fixture. But BacDive v2 is keyless, so `is_configured()` is
always True → golden would run against the **live network** in plain `make test`.
Fix: point the generated `build_weaver`/`make_weaver` at
`build_bacdive_weaver_fixture()` so they run offline. The static manifest/
fingerprint checks are unaffected (identical for the fixture build).
**Lesson:** the scaffold's tests + IMPLEMENTATION.md assume a configured/unconfigured
split that doesn't exist for keyless APIs. The guide should call this out and the
scaffold could detect `api_key="none"` + only-api backends and wire the fixture into
the generated tests automatically.

### 7. Root Makefile enumerates weavers by hand (doesn't scale)
Adding a weaver means editing the root `Makefile` in three places: the `test`
target's dependency list, a new `test-<name>` target, and `LINT_PATHS`. At 20-30
weavers this is error-prone. **Lesson:** make `test`/`lint` discover `weavers/*`
(glob the dirs / loop `$(MAKE) -C`), so a scaffolded weaver is picked up with no
root edits — matching how `members = ["weavers/*"]` already auto-discovers them.

### 8. Scaffold didn't add `httpx` though the api backend needs it
The generated `pyproject.toml` lists only `braidworks-core`; an `api` backend
inevitably needs an HTTP client, but it wasn't declared. Had to add `httpx>=0.27`
by hand. **Lesson:** when `backends` includes `api`, the scaffold should add
`httpx` to dependencies and the test extra (and maybe stub an injectable client).

### 9. Scaffold Makefile has no `test-live` target
The live E2E (`tests/test_e2e_live.py`, gated on `BRAIDWORKS_RUN_LIVE=1`) is a
standard pattern (taxon_weaver has it), but the generated per-weaver `Makefile`
only has `test`. Added `test-live` by hand. **Lesson:** generate a `test-live`
target (and the gated E2E stub) in the scaffold, at least for `api` backends.

<!-- append findings below as they come up -->
