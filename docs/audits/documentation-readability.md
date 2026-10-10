# Documentation readability: first pass

Date: 2026-10-10. Tracker: [#299](https://github.com/rafaelmdc/braidworks/issues/299).
This pass changes the entry points and current reader journey. The next review is
with the owner and will build three examples for real researcher tasks.

## Research and editorial decisions

[Diátaxis](https://diataxis.fr/) distinguishes learning, task instructions, explanation,
and reference. Applied here: the README introduces and demonstrates; usage guides
help readers do work; architecture explains; contracts and export/storage pages hold
technical detail. This is a content distinction, not a requirement to create four
new directory trees.

[Write the Docs](https://www.writethedocs.org/guide/writing/docs-principles/) emphasizes
current, discoverable, skimmable documentation and avoiding overlapping sources.
Applied here: a task-oriented index, links to maintained catalogues, separate current
guidance and dated designs, and removal of duplicated onboarding/API descriptions.

[Google's technical-writing guidance](https://developers.google.com/tech-writing/one/documents)
asks writers to identify audience and purpose and organize around readers' needs.
Applied here: explain inputs → source connections → outputs before introducing
framework classes; start with one bounded query; put configuration and contracts
where a reader can find them when needed.

These sources guide the organization. The findings below are repository observations,
not claims made by those sources. Runtime code, public signatures, and existing
acceptance evidence were used to reconcile behavior.

## Main findings and changes

| Finding | Evidence before this pass | First-pass action |
|---|---|---|
| README combines too many reading tasks | 336 lines spanning onboarding, executor code, result internals, expansion, tools, layout, and contributor reference | Reduced to 83 lines: purpose, mental model, one query, interface links, contribution and licensing |
| Navigation repeats the manual | `docs/index.md` includes its own Python setup and result buckets after linking another quickstart | Replaced with task routes and separate history links |
| Simplest Python entry point appears too late | README presents registry/plan/execute before `fetch`, whose first example needs AGORA local setup | Usage starts Python with `fetch`, explicit types, and an API-backed lookup; low-level code follows |
| General usage hides work beneath contracts | Table input, outcomes, archives, expansion accounting, and NCBI construction are mixed together | Usage covers tasks; result/export reference and persistence have dedicated pages |
| Persistence guidance contradicts itself | Usage says no supported resume while database/core docs expose `runs`, `resume`, SQLite cache and managed continuation | Documented current opt-in interfaces and distinguished cache, checkpoints, archives, and source reference databases |
| Architecture is stale despite claiming to be current reference | Discovery and TTLs called deferred; parallelism called future; result-bucket sum and singular/plural rules contradict later behavior | Rewrote current explanation and extracted a compact code-linked contract reference |
| Install instructions drift with versions | Hard-coded core 0.12.0 wheel and old source versions; four-source dependency selection for a two-source first query | Two-source start, explicit additive selection, browser setup, and version-independent local artifact patterns |
| Setup catalogue undersells current capabilities | Current core version stated as 0.12.0; recent reverse/hierarchy/reaction/archive surfaces absent | Updated all 17 source rows, practical interpretation, local prerequisites, and version guidance |
| Broad database page mixes unrelated storage systems | NCBI setup followed by generic lookup cache/run-store APIs and CLI reference | Kept taxonomy/reference operations there; moved generic storage details to persistence |
| Historical plans look like active instructions | Fan-out roadmap says later phases aren't built; audit entry points say delivery pending | Preserved evidence, added history notices, and refreshed current work status |
| Configuration reference lags implementation | AlphaFold archive options and MONDO mapping inputs missing from builder signatures | Refreshed existing signature blocks by introspection without constructing sources |
| Guidance disallows valid entry inputs | Implementation guide says never use raw entry keys and reachability requires an upstream producer | Clarified registered entry keys and direct-call reachability; conjunction-routing limit retained |
| Links/scripts repeat old instructions | Package/example README anchors point to removed sections; demo recommends environment-changing `uv run` and old export field | Repaired pointers, preserved selected environments, corrected demo comments/JSON field |

## Coverage and limits

The README and root Markdown guides under `docs/` were reviewed for audience,
sequence, duplication, current-vs-historical status, and prominent factual claims.
The full Markdown tree was inventoried; audit/refactoring records were treated as
historical evidence rather than rewritten line by line. Their entry points now
explain the later delivery/persistence context. Generated catalogues were inspected
and linked, not hand-edited.

Package READMEs were consulted for source behavior and broken entry-point links.
A full source-by-source editorial rewrite is still pending. Existing diagram exports,
the generated network HTML, and historical reproducibility scripts were inventoried;
this pass adds a small current architecture diagram without redesigning the assets.
The stress script remains diagnostic material, not a validated research tutorial.

| Documentation area | Treatment |
|---|---|
| README, index, installation, usage | Rewritten around the reader journey |
| Architecture, repo structure, sources | Current explanation/map/catalogue rebuilt |
| Database, pacing, builder configuration | Scope/status checked; storage separated; signatures refreshed |
| Release and migration guides | Kept task-specific detail; corrected superseded persistence claims |
| Original MVP, GUI, local-setup, fan-out, source roadmaps | Retained with explicit historical-status notices |
| Audit and refactoring trees | Inventoried; current-context notices at entry points; original evidence retained |
| Key index and network assets | Retained as generated reference; no manual catalogue edits |
| Example/package front-door links and demo script | Repaired for the new paths and environment guidance |

This is a first pass, not user-tested documentation or a complete API manual. Long
reference pages remain appropriate where readers need exact rules. The goal is to
make that detail optional during onboarding, not to delete contracts.

## Next joint review: three researcher examples

Choose the three scientific tasks together before writing them. Each should answer:

1. Who is doing this, what input data do they actually have, and what decision will
   the result support?
2. Which installed sources and prepared datasets are required, and why those sources?
3. What is the smallest working CLI/Python/browser path to a useful result?
4. What do the output columns mean, including missing data, evidence, and review?
5. What claims can the researcher make, and what does source coverage leave unknown?

Review the overview and first command from a new reader's perspective, then use
those examples to test navigation and terminology. Add verified compact summaries
to the README and full workflows elsewhere. Also inspect per-weaver README ordering,
browser labels/screenshots, export analysis examples, and dated diagrams with those
real tasks in mind. No invented research outputs or fixed live counts are needed.

## Verification

- Local links and heading anchors pass across the documentation tree, including
  GitHub `blob/main` links pointing back to this repository.
- Seven Python blocks in usage/results/database/persistence compile, including the
  explicitly documented notebook cell; public symbols import from the isolated env.
- Four exact Python query snippets execute with offline fixture sources. The managed
  query saves a checkpoint and its resolved result was loaded and verified.
- The first README command passes against live UniProt/PDBe: one resolved entity,
  both requested targets present, no missing fields or review flag.
- Both selected-source and browser installation commands pass `uv sync --dry-run`.
  No packages were installed/removed by these checks.
- `bash -n` passes for demo/stress scripts; `git diff --check` passes.

These are focused documentation checks; no browser usability trial, full environment
installation, full test-suite rerun, or source-by-source live recertification is claimed.
Runtime code, schemas, dependencies, package versions, and generated manifests are
unchanged. No new tools or biological reference databases are required for this edit.
