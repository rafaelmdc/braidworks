# Molecular weavers — build notes (scratch)

Running log of friction, gaps, and ideas hit while building the bioinformatics
demo weavers (UniProt hub + STRING / GO / PDB+AlphaFold / Reactome satellites, plus
the organism↔protein bridge). **Temporary** — to be triaged into weaverkit guidance /
backlog and then deleted, like `docs/bacdive-build-notes.md` was.

Tag legend: **[scaffold]** generated-code gap · **[framework]** core/weaverkit friction ·
**[guidance]** missing docs · **[good]** worked well · **[design]** weaver-design lesson.

## From `uniprot_weaver` (first molecular weaver)

1. **[scaffold] `weaver.spec.toml` → pyproject omits the entry-point block.**
   `weaverkit new` does not emit `[project.entry-points."braidworks.weavers"]`, so the
   weaver is invisible to `weaverkit view` / arq discovery / any registry-from-entry-points
   builder until added by hand. Both `weaver_id` and the builder name are known at
   scaffold time (`uniprot = "uniprot_weaver.factory:build_uniprot_weaver"`) → scaffold
   should generate it. (Same gap was logged for bacdive.)

2. **[scaffold] Scaffolded live-E2E ships a TODO placeholder that `--strict` can't catch.**
   `tests/test_e2e_live.py` is generated with `"TODO-real-input"` and a permissive
   `assert status in (OK, NO_MATCH)`. `verify --strict` only scans `src/` for placeholder
   markers, so a never-filled live test passes silently (it's skipped without
   `BRAIDWORKS_RUN_LIVE=1`). Ideas: seed the live test from the spec's `[[golden]]`
   (reuse its `input`/`expect`), or add a non-strict lint that flags TODO markers in
   `tests/`, or at least a louder reminder.

3. **[framework] Adding an *entry* key forces a core edit.** A new free-text entry
   (`protein.query`) must be a `SHARED_KEYS` member (conformance requires every
   `consumes` ∈ shared keys), and the weaverkit↔core lockstep parity test then forces
   adding it to core's `CANONICAL_TYPES` too — even though an entry key is never a join
   *target* and its canonical type is a trivial `str` pass-through. So a weaver author
   adding an entry key must edit **two** packages incl. core. Idea: recognize entry keys
   explicitly (an `ENTRY_KEYS`-style set that's exempt from the canonical-type parity, or
   auto-`str`), or a one-touch `weaverkit register-key` helper that edits all three sites.

4. **[design][guidance] "Representative selection" is a recurring problem with no support.**
   Like BacDive's type-strain choice, UniProt's "top reviewed hit" is **ambiguous and
   nondeterministic** for a bare cross-species gene symbol (every species' `TP53` is an
   equal `gene_exact` match; the API's relevance tie-break varies between calls, and
   `sort=annotation_score desc` deterministically picks the *wrong* species — hamster
   p53, snake insulin). **Determinism is a hard requirement** (same query → same protein
   every time). Resolution: (a) escalate accession → `gene_exact:` → free-text,
   reviewed-first; (b) request a ranked page with `sort=annotation_score desc`; (c) apply
   a **local total-order `_pick`**: highest annotation score, then accession ascending —
   so the result never depends on UniProt's unstable relevance ranking. Testing split:
   pin the **offline golden** to a fixed accession via the fixture; assert only
   **structural** truth in the **live** E2E (gene matches, reviewed, taxid is a positive
   int) plus one **accession** case that is exactly stable (`P04637` → 9606). Documented
   for users in the weaver README ("Deterministic representative selection"). Worth a
   short `implementing-backends.md` section: choosing a deterministic representative +
   this testing split, since BacDive hit the same shape.

5. **[good] The fixture + two-builder + `always_computed_groups` flow was smooth.**
   `vocab.py` generated correctly from the spec; `verify --strict` ran the golden offline
   on first try once the fixture + backend were filled. The injectable `client=` seam made
   both the unit test and the offline golden trivial. No changes needed to the generated
   `weaver.py` / `provider.py` / dispatch.
