# Diátaxis audit after M1–M4 (5.1)

Audit pass, 2026-11-09, for issue #337. It classifies every public page written or
changed in M1–M4, lists mixed-type pages and missing explanations, and records how each
finding was closed. The [October mapping](documentation-diataxis.md) is the baseline;
the [writing conventions](../../how-to/write-documentation.md) define the four types.

## Method

Every page under `docs/tutorials`, `docs/how-to`, `docs/reference` and
`docs/explanation`, plus the root README, the docs index and the notebooks, was
classified by reading its headings and the body of each section whose heading
suggested a second type. A page is *mixed* when a section serves a different reader
need (learning, doing, looking up, understanding) from the page's type and is longer
than a pointer. Short "see the reference" pointers are not findings. Examples were
re-run live where a finding depended on current source behaviour.

## Classification

| Page | Type | Verdict |
|---|---|---|
| tutorials/first-query-in-the-browser | Tutorial | Clean |
| tutorials/first-analysis-in-python | Tutorial | Clean |
| tutorials/protein-structures | Tutorial | Fixed: duplicated sentence; `why_missing` added to the column check (F5) |
| tutorials/microbial-functions | Tutorial | Clean |
| tutorials/disease-associations | Tutorial | Clean |
| notebooks/getting-started, notebooks/case-studies/* | Tutorial (runnable) | Clean; installs from PyPI, so blocked on the first release |
| how-to/install | How-to | Clean; catalogue link retargeted (F1) |
| how-to/run-queries | How-to | Clean |
| how-to/process-a-batch | How-to | Clean |
| how-to/follow-related-entities | How-to | Clean |
| how-to/find-a-field | How-to | Clean |
| how-to/work-in-python | How-to | Fixed in #372: stale review example |
| how-to/check-results | How-to | Fixed: `why_missing` step (F4) |
| how-to/use-the-browser | How-to | Clean |
| how-to/run-the-offline-demo | How-to | Clean |
| how-to/choose-sources | How-to + reference | **Mixed** → split (F1) |
| how-to/cache-and-resume | How-to | Fixed: engine-level Python section labelled, source-code link removed (F6) |
| how-to/set-up-ncbi-database | How-to | Clean; contract sections are already short pointers to reference/local-data |
| how-to/set-request-rates | How-to | Clean |
| how-to/implement-a-weaver | How-to (contributor) | Clean |
| how-to/release | How-to (maintainer) | Clean; updated in #370 |
| how-to/migrate-to-core-0.12, -0.13 | How-to (version-scoped) | Clean |
| how-to/write-documentation | How-to (contributor) | **Misfiled** in reference → moved (F2) |
| reference/sources | Reference | New (F1) |
| reference/python-api, cli/* | Reference (generated) | Clean; `make docs-check` guards drift |
| reference/results | Reference | Clean; `why_missing` documented in #374 |
| reference/browser, persistence, local-data, request-pacing, failures, discovery | Reference | Clean |
| reference/core-contracts, repo-structure | Reference (contributor) | Clean |
| reference/weaver-configuration | Reference | Clean; its example illustrates the interface, not a task |
| reference/keys-index, weavers-index.tsv | Reference (generated) | Clean |
| reference/index | Navigation | Fixed: catalogue rows retargeted, source-code link removed (F1, F6) |
| explanation/architecture | Explanation | Clean |
| explanation/how-routes-are-planned | Explanation | Clean |
| explanation/result-meaning | Explanation | Clean |
| explanation/where-data-comes-from | Explanation | New (F3) |
| README, docs/index | Navigation | Fixed: catalogue and explanation links (F1, F3) |

## Findings

| # | Finding | Resolution |
|---|---|---|
| F1 | `how-to/choose-sources` was half catalogue (a 17-row reference table, versions and attribution) and half task. | The catalogue, backend meanings and attribution moved to the new `reference/sources.md`. The how-to now covers checking with `doctor`, installing, setting up local data, verifying, and citing. Every catalogue link points at the reference page. **Closed.** |
| F2 | `reference/documentation-style` is a contributor guide with steps and templates, not facts to look up. | Moved to `how-to/write-documentation.md`; all links updated. **Closed.** |
| F3 | Missing explanation: nothing explained web APIs vs local databases vs bundled data, why some sources need setup, freshness, or why demo samples are not reference data. M4 (demo, case studies with local Disbiome) and the `why_missing` fix made this the most-needed concept page. | New `explanation/where-data-comes-from.md`, linked from the index, the catalogue and the how-to. **Closed.** |
| F4 | `how-to/check-results` told readers to inspect `missing` without the reason now available. | Step 2 mentions `why_missing`. **Closed.** |
| F5 | `tutorials/protein-structures` repeated a sentence fragment, and its column checklist omitted `why_missing`. | Both fixed. **Closed.** |
| F6 | User pages linked to engine source files (`persistent_query.py`, `query.py`) as if they were documentation, and the saved-run Python section did not say why it uses the engine API. | The links were removed and the section says that `Session` has a cache but no run store yet. The missing public API is a product gap, not a documentation one (follow-up below). **Closed for docs.** |
| F7 | The `work-in-python` review example had gone stale against live NCBI. | Fixed in #372 and verified live. **Closed.** |

## Follow-ups outside documentation

- A public Python API for saved runs would let `cache-and-resume` drop its engine-level
  script. Done afterwards: `Session(runs=...)`, `Session.resume` and `Session.runs`.
- After the first PyPI release, the tutorials' clone-and-sync setup becomes
  `pip install braidworks` (issue #335, 4.D).
