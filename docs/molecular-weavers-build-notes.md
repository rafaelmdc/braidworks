# Molecular weavers — build notes (scratch)

Running log of friction, gaps, and ideas hit while building the bioinformatics
demo weavers (UniProt hub + STRING / GO / PDB / AlphaFold satellites, plus the
organism↔protein bridge). **Temporary** — to be triaged into weaverkit guidance /
backlog and then deleted, like `docs/bacdive-build-notes.md` was.

Every finding carries a **→ where:** pointer (the file / scaffold template / test to
change) so a fix is actionable without re-deriving. Line numbers are hints (they
drift); the named symbol/template is the stable anchor.

Tag legend: **[scaffold]** generated-code gap · **[framework]** core/weaverkit friction ·
**[guidance]** missing docs · **[good]** worked well · **[design]** weaver-design lesson.

## From `uniprot_weaver` (1st molecular weaver)

1. **[scaffold] `weaver.spec.toml` → pyproject omits the entry-point block.** The weaver
   is invisible to `weaverkit view` / arq discovery / registry-from-entry-points until
   `[project.entry-points."braidworks.weavers"]` is added by hand. Both the weaver_id and
   the builder name are known at scaffold time.
   → where: template **`_PYPROJECT`** in `weaverkit/src/weaverkit/scaffold.py` (~L430) — it
   has no entry-points table. Add one rendered from the existing scaffold tokens
   (`{{WEAVER_ID}} = "{{DBWEAVER}}.factory:build_{{DBWEAVER}}"`). Symptom copy lives in
   every `weavers/*/pyproject.toml`.

2. **[scaffold] Scaffolded live-E2E ships a TODO placeholder that `--strict` can't catch.**
   The generated `tests/test_e2e_live.py` has `"TODO-real-input"` + a permissive
   `assert status in (OK, NO_MATCH)`; it's skipped without `BRAIDWORKS_RUN_LIVE=1`, so it
   can stay un-filled silently.
   → where: template **`_TEST_E2E_API`** in `weaverkit/src/weaverkit/scaffold.py` (written at
   ~L1320); `--strict`'s placeholder scan is **`_completeness_problems`** in
   `weaverkit/src/weaverkit/cli.py` (L91-103) and only walks the package `src/`
   (`pkg_dir.rglob("*.py")`), never `tests/`. Fix: seed the e2e from the spec's
   `[[golden]]` (reuse `input`/`expect`) in scaffold.py, or extend `_completeness_problems`
   to also scan `tests/test_e2e_live.py`.

3. **[framework] Adding an *entry* key forces a core edit.** A new free-text entry must be
   a `SHARED_KEYS` member (conformance requires every `consumes` ∈ shared keys), and the
   lockstep parity test then forces a matching `CANONICAL_TYPES` entry — even though an
   entry key is never a join *target* (trivial `str`).
   → where: gate in `weaverkit/src/weaverkit/conformance.py` (`check_manifest` reachability)
   against `SHARED_KEYS` in `weaverkit/src/weaverkit/keys.py`; parity test
   **`test_every_shared_key_has_a_canonical_type`** in `weaverkit/tests/test_conformance.py`
   forcing `CANONICAL_TYPES` in `braidworks-core/src/braidworks/core/keytypes.py`; plus
   `ENTRY_KEYS` in `weaverkit/src/weaverkit/index.py`. Fix idea: exempt entry keys from the
   canonical-type parity, or a `weaverkit register-key` helper that edits all sites.

4. **[design][guidance] "Representative selection" is recurring with no support.** Choosing
   one deterministic representative from an ambiguous match (UniProt's best ortholog,
   BacDive's type strain) has no shared helper or guidance, and the API's own ranking is
   often unstable.
   → where: hand-rolled in `weavers/uniprot_weaver/src/uniprot_weaver/backends/api.py`
   (`_pick` / `_best_hit`) and `weavers/bacdive_weaver/.../backends/api.py`
   (type-strain scan). Fix: a section in `weaverkit/docs/implementing-backends.md` on
   deterministic representative selection + the testing split (deterministic fixture golden
   vs structural live assertions).

5. **[good] Fixture + two-builder + `always_computed_groups` flow was smooth.** `vocab.py`
   generated correctly; `--strict` ran golden offline first try; the injectable `client=`
   seam made the unit test + offline golden trivial; no edits to generated `weaver.py` /
   `provider.py` / dispatch. → where (templates that worked): `_FIXTURE_API` (scaffold.py
   ~L821), `_FACTORY` (~L1028), `_WEAVER` (~L1001).

## From `string_weaver` (2nd molecular weaver)

6. **[scaffold] Entry-point block missing — again.** Same as #1.
   → where: same — `_PYPROJECT` in `weaverkit/src/weaverkit/scaffold.py`.

7. **[good] Single-input off a shared hub key just works.** Consuming
   `protein.uniprot.accession` made STRING reachable with zero ceremony; in the merged
   graph `uniprot → accession → string` is a real braid edge. The "consume a registered
   shared key" rule paid off. → where (mechanism): `BraidRegistry.build_graph` in
   `braidworks-core/src/braidworks/core/registry.py` + the shared-key gate. No fix.

8. **[design][guidance] HTTP status → WeaveStatus mapping is per-weaver guesswork.** STRING
   returns **404 for an unmappable identifier** — semantically a `NO_MATCH`, not an error.
   The natural `except httpx.HTTPError` lumps it into `record.error` (→ ERROR); the live
   "unknown input → NO_MATCH" test failed until I special-cased 400/404.
   → where: the stub's fetch guidance comment in template **`_BACKEND_STUB_API_KEYLESS`**
   `weaverkit/src/weaverkit/scaffold.py` (~L745) says "failures → record.error" but never
   mentions 4xx-as-not-found; the hand-written fix is in
   `weavers/string_weaver/src/string_weaver/backends/api.py` (`_resolve_one`, the
   `except httpx.HTTPStatusError` 400/404 branch). Fix: guidance in
   `weaverkit/docs/implementing-backends.md#fetch` + maybe a core helper that classifies
   `httpx.HTTPStatusError` (404/400 → not found, else error).

9. **[good] The live E2E caught a real semantic bug** (the 404 mis-classification) mocks
   couldn't — vindicates a real opt-in live test per weaver. Reinforces
   [[live-api-schema-drift-gap]]. → where: `weavers/string_weaver/tests/test_e2e_live.py`.

## From `quickgo_weaver` (3rd molecular weaver)

10. **[scaffold] Entry-point block missing — 3rd time; now a certainty.** Same as #1.
    → where: `_PYPROJECT` in `weaverkit/src/weaverkit/scaffold.py`. (Three for three —
    this should just be generated.)

11. **[design] "Many rows → distinct entities" aggregation is a recurring shape with no
    helper.** QuickGO returns one row per annotation *evidence* (≈1000 for p53) → dedup to
    distinct GO terms; Disbiome had many experiments per taxid; BacDive scanned many
    strains.
    → where: hand-rolled `_aggregate` in
    `weavers/quickgo_weaver/src/quickgo_weaver/backends/api.py`; analogous logic in
    `weavers/disbiome_weaver/.../backends/*` (join) and `weavers/bacdive_weaver/.../backends/api.py`.
    Fix: a shared "rows → distinct keyed records, sorted" helper (core or weaverkit) +
    guidance in `implementing-backends.md`.

12. **[design][guidance] Paginated APIs need a bounded-fetch pattern.** First weaver to
    paginate (page/limit up to a cap, `log()` on truncation); no scaffold support or
    guidance for "page until total or cap, accumulate".
    → where: hand-rolled `_all_annotations` in
    `weavers/quickgo_weaver/src/quickgo_weaver/backends/api.py`. Fix: a snippet/helper in
    `weaverkit/docs/implementing-backends.md` (and respect "no silent caps" — log truncation).

13. **[good] Empty-results = NO_MATCH worked out of the box.** Unlike STRING (#8), QuickGO
    returns `200 results:[]` for an unknown accession, which the generated `found=False`
    path already handles. Confirms #8 is specifically about non-2xx "not found" responses —
    a per-weaver decision. → where: the generated `LookupRecord(found=False)` contract in
    template `_BACKEND_STUB_API_KEYLESS` (scaffold.py).

## From `pdbe_weaver` (4th molecular weaver)

14. **[scaffold] Entry-point block missing — 4th time.** Same as #1; not re-litigating.
    → where: `_PYPROJECT` in `weaverkit/src/weaverkit/scaffold.py`.

15. **[good] The #8 lesson transferred.** PDBe also 404s an accession with no mapping;
    because finding #8 was logged, I wrote the `except httpx.HTTPStatusError` 404→NO_MATCH
    branch up front and the live test passed first try. Evidence that a one-line
    `implementing-backends.md` rule ("404/400 = not found, 5xx/network = error") would save
    the next author the round-trip. → where: same fix shape in
    `weavers/pdbe_weaver/src/pdbe_weaver/backends/api.py` (`_resolve_one`).

16. **[design] "Dedup → rank → cap, but count the true total" is the emerging house
    pattern.** STRING (score sort), QuickGO (distinct terms), PDBe (distinct structures by
    coverage/resolution) all: dedup to distinct entities, sort by a deterministic total
    order, expose a top-N list **and** a true total count, plus a full records blob. This is
    now consistent enough across 3 weavers to bless as guidance (and is the natural home for
    the #4/#11 representative + #12 pagination helpers).
    → where: `_extract`/`_pick` in the api backends of `weavers/{string,quickgo,pdbe}_weaver`;
    propose codifying in `weaverkit/docs/implementing-backends.md` (+ optional shared helper).
