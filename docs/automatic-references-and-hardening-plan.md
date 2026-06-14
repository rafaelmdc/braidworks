# Automatic references + weaverkit hardening — implementation plan (scratch)

**Temporary** working plan, like `molecular-weavers-build-notes.md`. Delete once all
brackets land. Agreed with user 2026-06-14.

## Context / why

License + citation data already lives in every `weaver.spec.toml` (`license`,
`source_url`) but as a **free-text string used only at scaffold time** to fill the
README — it never reaches the runtime `WeaverManifest`. So after a braid runs there is no
way to know which sources were touched and cite them. Reactome already overloads the
field: `"CC0 (Reactome; cite https://doi.org/10.1093/nar/gkab1028)"`.

Issue #1 ("automatic references based on license preferences in metadata") = make this
structured + queryable at runtime, and auto-emit citations whose **form is driven by the
license** (CC0 = cite requested, CC-BY = attribution required, proprietary = warn). Plus
fold in the worthy `molecular-weavers-build-notes.md` findings (#1-#21) and feed issue
#39 (Agents.md) / set up issue #38 (visualizer info blocks).

User decisions (2026-06-14, AskUserQuestion):
- **References surface in 3 places:** braid results at runtime, a CLI command/report,
  and the visualizer (shown when a specific weaver is selected).
- **"License preferences" = license → citation form** (a license→requirement table).
  NOT user allow/deny of licenses at plan time.

## Permissions / process

- User granted: commit, PR, **and merge into main** — so everything MUST pass tests
  before merge. Run `make verify` / weaver `make test` + workspace tests.
- **One PR per bracket**, but **multiple well-scoped commits per PR** (not monolithic) —
  split for review/dev sanity.
- Tags: per `[[git-tag-on-release]]`, create+push `<pkg>-v<version>` at each merge commit
  for any version bump (core, weaverkit, weavers). Underscore for weavers, hyphen for
  platform.
- No `Co-Authored-By` trailer on commits (per [[commit-attribution-preference]]); PR-body
  "Generated with Claude Code" line is fine.

## Brackets (one PR each)

### Bracket 1 — metadata foundation  ← START HERE
Goal: structured license/citation in the spec, plumbed to runtime, retrofit all weavers,
verify guard. No reference *emission* yet (that's bracket 2).

- **A.1 Spec structure** (`weaverkit/src/weaverkit/spec.py`)
  - Add structured fields to `WeaverSpec`: keep `license` (move toward SPDX id like
    `CC0-1.0`), add `citation` (DOI/text, optional). Keep `source_url`.
  - Parse `[weaver].citation` from TOML; validate in spec.py's field checks.
  - A `LICENSE_RULES` table (new, in weaverkit) mapping license id → citation
    requirement: `cite_requested` / `attribution_required` / `restricted`. This table IS
    the "license preferences."
- **A.2 Runtime plumbing**
  - `braidworks-core/.../capability.py`: add a `Provenance` (or `source`) block to
    `WeaverManifest` (source_url, license, citation) with `to_json`/`from_json`.
  - Generate it into each `vocab.py` `build_manifest`. Update scaffold `_VOCAB` template +
    `_PYPROJECT`/README tokens as needed so new weavers get it.
  - core version bump (+ tag at merge).
- **A.1-retrofit** all 9 weaver specs (`weavers/*/weaver.spec.toml`): split the license
  string into `license` + `citation`. Regenerate each `vocab.py`. Weaver patch bumps
  where the manifest changes (+ tags).
- **A.4 Guard** (`weaverkit/src/weaverkit/cli.py` verify): warn when license missing /
  not in `LICENSE_RULES`, or citation missing for an attribution-required license.
- Tests: spec parsing, manifest provenance round-trip, conformance still green, all
  weaver `make test`.

Commit split (suggested):
1. core: `Provenance` on `WeaverManifest` (+ tests, version bump)
2. weaverkit: `WeaverSpec.citation` + `LICENSE_RULES` + spec validation (+ tests)
3. weaverkit: scaffold templates emit provenance + verify guard (+ tests)
4. retrofit all weaver specs + regenerate vocab (mechanical)

### Bracket 2 — reference emission (runtime + CLI)
- Runtime: braid result exposes a deduped, deterministically-ordered bibliography of
  sources actually touched, rendered per `LICENSE_RULES`. (Find where results aggregate —
  likely `braidworks-core/.../braid.py`.)
- CLI: `weaverkit references` (selected weavers / a path) — reuse view.py discovery.
- Tests for both.

### Bracket 3 — scaffold hardening (no retrofit of shipped weavers; low risk)
- B.1 Generate entry-point block — `_PYPROJECT` in scaffold.py (#1/#6/#10/#14)
- B.2 `make tag PKG= VERSION=` target + scaffold "next steps" checklist line + `verify`
  warning for untagged current version (#21)
- B.3 `_completeness_problems` (cli.py) also scans `tests/test_e2e_live.py` so the
  placeholder fails `--strict` (#2)

### Bracket 4 — guidance (issue #39 Agents.md + #3)
- B.4 Fetch-pattern section + a shared HTTP-status classifier helper
  (`httpx.HTTPStatusError` → 404/400 = NO_MATCH, 5xx/network = error); retrofit the 5
  molecular backends to use it. Document in AGENTS.md / implementing-backends.md
  (#4/#8/#11/#12/#16/#17/#18).
- B.5 Exempt entry keys from canonical-type parity, or `weaverkit register-key` helper (#3).

### Bracket 5 — visualizer (issue #38, separate track, depends on bracket 1)
- Per-weaver info block (source/license/citation/join keys/capabilities/links) shown on
  selection.
- Dynamic scrollable weaver list; standardize help/description backbone.
- "Giant tower" layout refactor (nodes all aligned → single stack); rethink node grouping.

## Cleanup
After brackets land, delete `molecular-weavers-build-notes.md` and this file; close
issues #1, #38, #39 (and update memory).
