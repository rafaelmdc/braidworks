# Audit 05 remediation spec

Status: audited requirements; current remediation status is in ../README.md and matching plans; evidence confidence remains as stated below. Source audit: ../reports/05-docs.md. Each finding has stable ID A05-NN. Full source evidence, limitations, strengths and open questions are preserved below. This is a remediation specification, not a weaver.spec.toml or a request to weaken contracts.

## Requirements index

| ID | Requirement/problem | Status |
|---|---|---|
| A05-01 | The recommended next task is already implemented | fixed: see matching plan evidence |
| A05-02 | Published weaver inventory is incomplete and stale | fixed: see matching plan evidence |
| A05-03 | Root README contains an obvious generated markup artifact | fixed: see matching plan evidence |
| A05-04 | Core package dependency description is inaccurate, and package install guidance is incomplete | fixed: see matching plan evidence |
| A05-05 | User docs promise complete, mutually exclusive outcomes and fan-out without qualifying known limits | fixed: see matching plan evidence |
| A05-06 | Documentation map mixes audiences and fails to identify a current user path | fixed: see matching plan evidence |

## Preserved audit evidence

# Documentation quality audit

## Executive assessment

The repository has substantial documentation and good practical examples, but a first-time reader can be misled by a stale flagship roadmap, outdated source inventory, and user-facing guarantees that exceed current behavior. The root README also ends with a visible template artifact. Public documentation is primarily workspace-oriented; the package READMEs do not yet give an outside-workspace reader a complete install path or make the split between core and source packages clear enough. I found no missing relative link targets in the sampled top-level/package docs.

This is a bounded static audit. I did not run tests or live API examples. I reused the earlier architecture and feature audits for runtime claims, especially the result-bucket and fan-out behavior. The coordinating agent reported that full dependency setup is currently blocked by missing compiler/Python headers.

## Strengths worth preserving

- The root README starts with a bench-biologist workflow and gives shell and Python entry points, species pinning, batch files, output formats, and a fan-out example.
- `docs/usage.md` explains backend choices and local NCBI database setup with concrete commands.
- `weaverkit/README.md`, root `AGENTS.md`, and the implementation guide establish a repeatable spec/scaffold/implement/verify path and emphasize real source samples and provenance.
- Per-weaver READMEs expose source, license, and citation metadata; FAPROTAX explicitly distinguishes its custom upstream data terms from a nearest registry identifier.
- Most sampled relative links resolve, including package README links into the workspace.

## Numbered findings

### 1. The recommended next task is already implemented

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed. **Effort:** S.

**Evidence:** `docs/NEXT.md:21-36` recommends adding UniProt `resolve_mapping` for `gene.ncbi.id → protein.uniprot.accession`, and says that edge is missing. The current capability is `map_to_accession`, declared at `weavers/uniprot_weaver/weaver.spec.toml:92-101` and implemented in `weavers/uniprot_weaver/src/uniprot_weaver/backends/api.py:310` (source location also recorded in Audit 04). `docs/NEXT.md:3-4` dates the page to 2026-06-15 and core 0.7.1; current package metadata is core 0.11.3 (`braidworks-core/pyproject.toml:3-4`).

**Impact/reasoning:** A maintainer following the “start here” page can duplicate shipped work and miss the actual remaining acceptance work. The page is explicitly an orientation document, so its first recommendation should be checked against current manifests before directing work.

**Smallest useful remedy:** Replace the gene→protein bridge proposal with current demonstrated gaps and mark historic live observations as dated until rechecked. Treat current specs and generated indexes as inventory inputs, not the old prose list.

**Validation:** The recommended task must not duplicate a registered capability; its workflow and version claims agree with current package metadata and source specs.

### 2. Published weaver inventory is incomplete and stale

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed. **Effort:** S.

**Evidence:** Root `README.md:168-180` lists ten sources and omits sources present in the repository, including GTDB, GMrepo, MONDO, FAPROTAX, AGORA, Wikidata, and Wikipedia. `docs/index.md:3` also presents a short hand-selected list. `docs/NEXT.md:12` says nine weavers ship, while the current repository has 17 source specs. `docs/weavers-index.tsv` also omits GMrepo and MONDO; their current specs are `weavers/gmrepo_weaver/weaver.spec.toml:50` and `weavers/mondo_weaver/weaver.spec.toml:40`. Audit 04 independently parsed 17 specs and recorded the count.

**Impact/reasoning:** Users cannot tell which packages are available, and maintainers can mistake a missing index row for an unimplemented source. The root README currently calls its list “What you can ask for (the weavers),” which reads as a catalogue rather than a selected subset.

**Smallest useful remedy:** Label the README list as selected/keyless examples and link to a complete generated catalogue, or regenerate and publish the complete inventory. Make the `make index` output part of the release checklist when manifests change.

**Validation:** Every installed source appears in the complete inventory with its setup requirement; generated TSV and human key index match current specs.

### 3. Root README contains an obvious generated markup artifact

**Category:** first-release improvement. **Severity:** low. **Confidence:** confirmed. **Effort:** S.

**Evidence:** `README.md:314-315` ends with literal `</content>` and `</invoke>` tags following the documentation table.

**Impact/reasoning:** These tags look like leaked tool/template markup and make the repository’s main entry page appear unfinished.

**Smallest useful remedy:** Remove the two literal tags and ensure the document ends after the table.

**Validation:** Render the README in a Markdown preview and confirm no artifact appears after the documentation table.

### 4. Core package dependency description is inaccurate, and package install guidance is incomplete

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed. **Effort:** S–M.

**Evidence:** `braidworks-core/README.md:3-5` says “Pure stdlib plus `networkx`,” but `braidworks-core/pyproject.toml:7-8` also requires `platformdirs>=4.0`. `braidworks-core/README.md:25-28` says installing core puts the `braidworks` CLI on PATH and points to workspace-relative docs; it does not explain that core alone contains no source weavers, nor give an install command for a useful source package. The root user path (`README.md:29-37`) instead clones the monorepo and runs `uv sync --all-extras`.

**Impact/reasoning:** Users installing the published core package outside the checkout may conclude the base dependency set is stdlib-oriented, then find the CLI has no useful sources to discover. Package README relative links into `../docs` and `../README.md` also do not resolve from a wheel or an isolated package checkout.

**Smallest useful remedy:** State the actual runtime dependencies and give an outside-workspace installation example that installs core plus selected published weaver distributions (if supported by the release layout). Link to hosted docs for installed-package readers; keep workspace-relative links as contributor conveniences.

**Validation:** Follow the documented commands in a clean directory outside this workspace and confirm `braidworks weavers` discovers at least the documented source set; documentation accurately names installed dependencies.

### 5. User docs promise complete, mutually exclusive outcomes and fan-out without qualifying known limits

**Category:** release blocker for the advertised completeness guarantee; first-release improvement for fan-out wording. **Severity:** high. **Confidence:** confirmed from prior bounded implementation audit. **Effort:** M.

**Evidence:** `README.md:126-136` and `docs/usage.md:110-124` say every input is in exactly one mutually exclusive bucket and that bucket lengths equal input count. The earlier architecture audit confirmed serialized partial-success errors can be counted twice and can change fatality after JSON round-trip (Audit 01 finding 4). `README.md:196-215` and `docs/usage.md:138-159` describe fan-out as one child per member and present `max_expansion` as a safety cap; Audit 01 finding 5 confirmed expansion constructs cross-products before applying the cap, applies the cap per input chunk, and silently drops truncated leaves from result accounting. `docs/architecture.md:490-501` repeats the exact bucket invariant.

**Impact/reasoning:** Bench users may treat output row/bucket totals as a complete accounting of inputs and fan-out leaves, despite duplicate counts or invisible truncation. This can distort spreadsheet coverage and make an apparently finished result incomplete.

**Smallest useful remedy:** Once implementation behavior is settled, make result documentation describe partial branch completion and truncation explicitly, including where callers can inspect status and counts. Until then, remove unconditional “exactly one,” equality, and “one child per result” guarantees from public quickstarts.

**Validation:** Serialize/deserialize partial-error results and exercise fan-out above a small cap; documented bucket totals and truncation indicators match observed results and preserve input lineage.

### 6. Documentation map mixes audiences and fails to identify a current user path

**Category:** first-release improvement. **Severity:** low–medium. **Confidence:** confirmed. **Effort:** S.

**Evidence:** `docs/index.md:7-21` combines user usage, architecture, historical implementation plan, an implemented local setup plan, roadmap, generated inventories, agent implementation guide, AGENTS, and contributor docs in one undifferentiated list. The `docs/NEXT.md` page linked from roadmap context is stale per finding 1. Root `README.md:300-313` similarly presents concepts, operational inventories, internal contributor contracts, and implementation references in one flat table.

**Impact/reasoning:** New users are sent toward internal plans alongside tutorials, while contributors have no compact entry point distinguishing recipes/reference from internals. Historical plans marked historical are useful but still compete with current user instructions.

**Smallest useful remedy:** Use a short map with four groups: tutorials (install, first query, batch/export); how-to recipes (local NCBI, fan-out, parameters); reference (CLI, keys, licenses/provenance, package catalogue); contributor internals (architecture, spec/scaffold guide, AGENTS, roadmaps). Label historical plans and avoid promoting them in the first-run path.

**Validation:** A new reader can identify the one first-run tutorial, a task-specific recipe, the authoritative CLI/reference page, and the contributor build guide from `docs/index.md` without opening a stale planning document.

## Documentation map proposal

| Audience | Primary docs | Role |
|---|---|---|
| Bench users | Root README quickstart; `docs/usage.md`; `examples/README.md` | Install, species-pinned query, batches, result interpretation |
| Task recipes | `docs/database.md`; a concise fan-out / batch export recipe | Local data, expansion, practical limits |
| Reference | CLI reference, keys catalogue, weaver/source catalogue, provenance/licensing | Exact options and source requirements |
| Contributors | `CONTRIBUTING.md`; `AGENTS.md`; `weaverkit/README.md`; implementation guide; architecture | Development workflow and contracts |

Roadmaps and historical plans should be visibly dated and kept outside the primary first-run navigation.

## Verification log

- Read root `AGENTS.md`, `.audit-local/COMMON.md`, assigned prompt, and prior reports 01–04.
- Inspected root README, core and weaverkit READMEs, docs index/usage/NEXT/roadmap/architecture/fan-out guide/implementation guide, examples, contributor guide, relevant metadata, and Makefile.
- Ran a bounded standard-library relative-link target scan across the sampled main docs; it reported no missing relative file targets. This does not validate anchors or external URLs.
- Confirmed root README trailing artifact with `rg` and line-numbered source.
- Compared the key stale roadmap and inventory statements to current specs/metadata and reused Audit 04's 17-spec inventory rather than independently running the workspace registry.
- No tests, live APIs, link network checks, package installation, or document edits were performed. Full dependency setup was unavailable per coordinating agent's environment report.

## Top five actions

1. Replace `docs/NEXT.md`'s already-implemented UniProt bridge recommendation with current acceptance gaps.
2. Clarify the result accounting and expansion guarantees after the runtime defects are addressed.
3. Publish a complete generated source catalogue and label any short README list as selected examples.
4. Fix public package README dependency/install guidance for readers outside the monorepo.
5. Remove the README markup artifact and reorganize docs index by audience and task.

## Open questions and limitations

- Which published package names and installation combinations will be supported for a first release? The package docs need that release policy to provide exact external install commands.
- Should partial branch outcomes and fan-out truncation be documented as separate status fields, a sidecar, or result metadata? Documentation should follow the chosen public contract.
- External URL availability, package index publication, and upstream license terms were not independently verified.
- The link scan checked local path existence, not Markdown anchors, hosted rendering, or outbound links.
