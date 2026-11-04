# Human usability audit

## Executive assessment

The CLI and Python API offer a credible molecular workflow, and the browser provides useful graph exploration, typed parameter controls, route inspection, citations, and spreadsheet downloads. The README gives a concrete TP53 example and a batch input file, reducing the first-command barrier substantially.

The browser is not yet a dependable substitute for that workflow: its two run paths differ in species parameter support, review-needed inputs disappear from its summary/table, saved recipes do not preserve a graph-built experiment, and generated code does not preserve selected settings. These are task obstacles rather than aesthetic objections. A public release can retain the current graph and typed-key model while making these boundaries explicit and preserving experiment settings and outcomes.

This is **source inspection plus isolated Python helper execution**, not a browser interaction or live biology validation. The installed workspace was unavailable: `.venv/bin/python` could not import networkx; the parent reported dependency synchronization blocked by missing compiler/Python headers. No installation or production edit was performed here. Audits 01–04 were consulted; CLI defects and stale documentation are cross-referenced rather than reassessed as new findings.

## Strengths worth preserving

- README.md:47–83 provides a species-constrained TP53 query, sample batch file, spreadsheet export, and structure drilling, with literal commands instead of only abstract definitions.
- `braidworks-core/src/braidworks/core/cli.py:659–704` makes input files, repeated constants, expansion, parameters, and strictness discoverable in subcommand help; `:572–585` lists declared parameter descriptions/defaults.
- `weaverkit/src/weaverkit/view.py:85–92` carries type descriptions into graph cards; `_view_template.py:721–742` exposes source provenance, licenses, backends, and fan-out. Keep software licensing distinct from these upstream data license labels.
- `_serve_ui.py:640–658` renders enum, bool, and numeric parameter controls with descriptions. `_serve_ui.py:423–432` retains every requested target column, including blank columns, and offers intermediate fields through a toggle.
- `serve.py:144–155` preserves individual error messages and entity/capability context; `_serve_ui.py:444–452` displays them instead of only “no results.” Optional server dependencies have a direct installation hint (`serve.py:42–45`).
- `weaverkit/tests/test_serve.py:64–154,193–227` contains deterministic planning/run tests and HTTP smoke tests. These are a useful base, although they do not exercise actual user interaction or species settings through both UI paths.

Unqualified `serve.py`, `view.py`, `_serve_ui.py`, and `_view_template.py` filenames below refer to `weaverkit/src/weaverkit/`.

## Journey walkthroughs

| Journey | Steps and knowledge required | Discoverability, feedback, recovery, and success |
|---|---|---|
| First TP53 query, human only | Read README; learn `protein.query`, desired `go.biological_process`/`protein.interaction.partners`, and human taxid 9606; CLI uses `--param organism=9606`. Browser graph mode selects the input node, picks leaf outputs from weaver menus, waits for route preview, and edits the resolver's organism card. | README is concrete. Graph search does not search leaf output names/descriptions (finding 6). Typed Plan→Run and traversal omit access to the necessary resolver settings (finding 1). Success is human accession plus requested annotations with effective species visible, not simply nonempty fields. |
| Preview and run a route | CLI `keys`/`weavers` identify IDs; `path --from … --to …` previews; `weave --have … --want …` executes. Browser offers a graph preview or advanced Have/Want fields and Plan. | Names and backends are visible; input value is entered only after advanced planning. Preview controls and generated code do not capture all run settings (finding 4). Graph no-route preview has no textual explanation (finding 8). Python `fetch` removes planner boilerplate but requires `have="protein.query"` for this molecular journey because its default is taxid (`fetch.py:35,116`). |
| Batch gene input → spreadsheet | Use sample `examples/genes.txt`, `--in-type protein.query`, organism parameter, targets, and `--format tsv > out.tsv`. Header-based input instead requires type-ID column names. | CLI has a concrete recipe. Browser accepts one Have dictionary for one entity and has no upload/paste batch workflow (finding 9). Audit 03 covers stdin/table planning defects and missing export outcomes. Success is one accountable outcome for every input with identifiers/status retained, including missing/review/error cases. |
| Accession → individual PDB descriptions | Start from accession (or `protein.query=P04637`); request structure title/method; CLI explicitly uses `--expand all`. Browser advanced run has top 1/top k/all; graph run silently uses top 1 unless a pass-through is selected. | Fan badges and pass-through menus explain one→many topology. Graph controls conceal how many records will be drilled (finding 7); default table hides PDB identifier and flattened rows lose parent identity (finding 2). Success is individually identifiable structures with a clear bound and originating protein. |
| NCBI gene orthologs → protein annotations | Start `gene.ncbi.id`; explicitly traverse `ncbi.list_orthologs`, then request protein outputs; potentially set `taxon_filter`. Need to understand that traversal changes which entity is annotated. | Spec declares a gene-ID set; UniProt accepts gene ID as an alternative mapping input. Graph pass-through exists, but traversal preview is skipped and graph execution always expands all (findings 1,7). Success is distinguishable ortholog genes/proteins with species/lineage and parent input; no actual backend execution was performed here. |
| Partial/no/ambiguous results and failures | CLI human summary/strict and executor/Python buckets require reading their semantics. Browser table shows requested columns, optional intermediate columns, aggregate resolved/unresolved/errors, and error messages. | Blank targets can indicate partial enrichment; there is no review queue summary/table or explanation of which requested targets are missing (finding 2). API network failures have actual message display, but SSE transport failure has no explanation (finding 8). Recovery means knowing whether to correct input, select a candidate, configure a backend, or retry. |

Declared single-key paths were independently checked from TOML specs: protein.query→UniProt→QuickGO processes; protein.query→UniProt→STRING partners; accession→PDBe structures→PDBe descriptions. NCBI orthologs emits gene.ncbi.id (`weavers/ncbi_weaver/weaver.spec.toml:217–221`) and UniProt map-to accepts it. These are **type-level reachability**, not installed planner success, biological truth, or evidence of complete coverage. Audits 01/04 cover underlying traversal and mapping risks.

## Numbered findings

### 1. Browser run modes do not consistently expose or apply species restrictions

**Category:** release blocker for presenting GUI as equivalent to the flagship CLI workflow. **Severity:** high. **Confidence:** confirmed source path; browser behavior not exercised. **Effort:** M.

**Evidence:** `_serve_ui.py:626–636` obtains controls only from graph pass-throughs and `lastRoutePath`; advanced `runPlan` (`:495–517`) does not assign that preview state. `runBraid` builds an SSE query with have/want/policy/expand/k but no params (`:390–395`); `serve.py:367–405` has no params argument and executes without params. Graph `runBuild` forwards `collectParams()` (`_serve_ui.py:835–843`). Traversal preview is skipped at `:734`, so its resolution/final route parameter-bearing steps cannot be discovered by that preview.

**Impact/reasoning:** A biologist choosing advanced Have protein.query / Want GO processes has no supported way to pin TP53 to human before that run. A graph-built gene/name→ortholog traversal cannot reliably configure resolver-prelude species through those cards. The actual species parameter says unset means any (`weavers/uniprot_weaver/weaver.spec.toml:59–62`). This is distinct from Audit 03's CLI scope-validation defect.

**Smallest remedy:** Share effective-route parameter discovery and transport across both run modes, including traversal prelude/final steps; display effective settings with results. Until then, explicitly direct species-sensitive typed/traversal GUI use to a working supported path.

**Validation:** A deterministic recording resolver receives organism=9606 from graph, advanced and traversal-prelude runs; clearing it yields an explicitly visible unset value; verify request bodies and rendered controls. No live API is needed.

### 2. Browser results cannot account for review inputs or identify exported leaves

**Category:** first-release improvement. **Severity:** high. **Confidence:** confirmed isolated helper execution and source inspection. **Effort:** M.

**Evidence:** `serve.py:131–141` flattens only resolved strand values, removing entity_id/parent_id; `:180–184,289–293` summaries omit review_queue. `_serve_ui.py:440–443` displays no review count; `:478–482` exports flattened rows, and delimited export defaults to requested target columns. The raw execution JSON remains available in the server payload but the export does not use it.

**Impact/reproduction:** Running the unchanged `_rows` body on one resolved child with parent, one unresolved, one review and one error returned only `[{'structure.pdb.title': 'title'}]`. Identity, parent and all other outcomes disappeared. A title-only CSV after structure drilling cannot identify which PDB produced each row. An ambiguous input can yield no table rows and no review indication. Audit 03 covers analogous CLI export issues; this finding addresses the browser's separate transformation.

**Smallest remedy:** Keep input/entity/parent identifiers and outcome status as table/export metadata, include review count and candidate/review context, and explain missing requested fields per row. Allow requested-target filtering without suppressing essential identity/outcome metadata. Export diagnostics/references in a structured JSON envelope if desired.

**Validation:** A mixed successful/partial/no-match/review/error fixture and a fanned structure fixture retain every relevant outcome, target coverage, PDB identifier and parent in both displayed and exported data; review is distinguishable from absence.

### 3. Saving a graph-built recipe silently ignores that experiment

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed source path. **Effort:** S–M.

**Evidence:** Graph selection lives in `build.have`, `build.through`, `build.want` (`_serve_ui.py:575`); `saveRecipe` instead reads advanced `b-have`/`b-want` and silently returns when both are empty (`:551–558`). Saved records contain only have/want/policy; no params, expansion or traversal. `loadRecipe` restores those fields and calls advanced planning (`:564–570`).

**Impact/reasoning:** A first-time user builds and runs a route on the graph, enters a recipe name, and clicks Save: fresh advanced fields are empty, so nothing is saved and no explanation appears. If advanced fields contain an old plan, Save can save that different plan. Species restrictions and pass-throughs are not reproducible after saving.

**Smallest remedy:** Save from the active experiment model, include parameters/traversals/expansion, and acknowledge successful save or validation failure. Explicitly identify what is preserved.

**Validation:** Save/load a graph TP53 human recipe and an ortholog traversal; compare effective plan/input-type settings and params before/after. Fresh graph save visibly succeeds, and an invalid save explains why.

### 4. “Generated code” does not preserve the selected experiment settings

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed helper execution and source inspection. **Effort:** S–M.

**Evidence:** `serve.py:51–75` generates type-only CLI/Python templates; `plan_response` emits them without using selected policy (`:111–117`). CLI templates omit parameters/expansion; Python still requires registration of an undefined registry (`:68–70`) and top-level await. `_serve_ui.py:270–284` presents these as Run (CLI)/Python with copy controls.

**Impact/reproduction:** Actual helper output was `braidworks weave --have protein.query=<value> --want go.biological_process`. It provides no species parameter even if the GUI experiment is human-constrained, and no all-expansion for structure drilling. Selecting local-only in GUI can produce a default-policy command that uses an API. An occasional Python user cannot paste the snippet into a normal script and run it as presented.

**Smallest remedy:** Generate from effective run settings; label placeholder templates clearly; provide a complete synchronous `fetch` example for applicable simple routes or an asyncio entry point plus discovery for advanced ones. Preserve policy where the interface supports it; otherwise mark the unsupported translation explicitly.

**Validation:** Copy each supported recipe into a deterministic CLI/Python fixture harness and compare effective species, expansion and backend choice; unresolved placeholders are visibly identified.

### 5. Core graph and modal actions lack keyboard/accessibility equivalents

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed markup/event inspection; assistive technology testing needed. **Effort:** M.

**Evidence:** `_view_template.py:161` renders a canvas without accessible graph content; graph interaction is mouse handlers (`:590–616`). Weaver rows are clickable divs (`:691–701`), chip removal clickable spans (`_serve_ui.py:582–587`), and code tabs clickable spans (`:278–280`). The result/code sheet lacks dialog role/name/modal semantics (`:212–216`) and `openSheet`/`closeSheet` only changes hidden/content (`:254–259`). Parameter labels at `:657` are siblings with no `for` association; many inputs use adjacent spans/placeholders.

**Impact/reasoning:** Keyboard-only users cannot select the graph's input/output/pass-through nodes or remove chips via normal focus controls. Opening results does not place focus in the sheet or return it on close. The advanced text mode partly substitutes for graph selection but does not provide equivalent traversal/species controls. Escape dismissal and native buttons elsewhere are useful existing support.

**Smallest remedy:** Add a keyboard-accessible node/output/pass-through list using native controls; associate labels, use buttons for actions, and give sheets appropriate dialog semantics with focus entry/return and containment.

**Validation:** Complete TP53 human and PDB drilling using only keyboard; inspect accessible names and dialog focus behavior with a browser accessibility tree. Source inspection alone cannot certify screen-reader usability or contrast.

### 6. Searching for the desired biological attribute does not find hidden output fields

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed source reasoning. **Effort:** S.

**Evidence:** `view.py:129–145` keeps leaf output fields off graph nodes and on operation payloads. `_serve_ui.py:528–532` searches only node label/key/weaver/capability, not output_leaves or descriptions. Output picker exposes exact type IDs (`:776–781`); CLI keys lists IDs/producers/consumers without registry descriptions (`braidworks-core/src/braidworks/core/cli.py:606–620`). Existing human descriptions are available in `weaverkit/src/weaverkit/keys.py:13–53` and OUTPUT_KEYS.

**Impact/reasoning:** Searching `biological_process` cannot identify the QuickGO operation from its label `quickgo / list_go_terms`, even though it produces that desired leaf. A user must already know which database owns the output, or its exact type ID for the advanced field. This obstructs choosing targets, rather than merely preferring friendlier terminology.

**Smallest remedy:** Include output names and existing descriptions in graph search, indicate the matching output in the picker/card, and expose descriptions in CLI inspection where feasible without domain dependencies in core.

**Validation:** Searching biological_process, interaction partners, and structure title reveals the producing operation/output; exact IDs continue to work; simple input descriptions distinguish gene symbol from NCBI gene ID.

### 7. Graph fan-out has no visible bound control before running

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed source path. **Effort:** S–M.

**Evidence:** `_serve_ui.py:843` forces graph execution to all when any traversal exists and top otherwise, k=5; graph controls at `:163–167` contain no expansion choice. Advanced mode does provide top 1/top k/all (`:356–359`). CLI documents ordinary default none versus traversal all (`braidworks-core/src/braidworks/core/cli.py:690–698`).

**Impact/reasoning:** A graph-built accession→structure description route drills only the top member unless the user discovers pass-through selection. A pass-through can instead expand every ortholog without a visible bound. The UI modes therefore differ in result cardinality, runtime and upstream request volume; users cannot predict whether they obtained one member or all from the graph Run controls alone.

**Smallest remedy:** Expose the existing expansion choice beside graph Run, explain how it changes downstream rows, and show the selected bound/effective fan policy with results. Avoid a new planning system.

**Validation:** A deterministic five-member set produces 1, K, or all identifiable descriptions under each choice in both UI modes; traversal settings are explicit before execution.

### 8. Failed graph previews and stream disconnects provide no actionable feedback

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed source path. **Effort:** S.

**Evidence:** Graph preview failures clear highlighting/route state without showing `d.error` (`_serve_ui.py:744–753`), with an explicit comment that the visual gap represents no route (`:724–727`). `es.onerror` closes the stream and re-enables Run without calling showError (`:406`). By contrast, explicit SSE error events and normal POST failures display messages (`:404,847–854`). Backend choice is a policy selector (`:189–195`), with no readiness/configuration summary in the inspected payload/card paths (`view.py:136–146`; `_view_template.py:725–730`).

**Impact/reasoning:** A full undimmed graph gives no textual distinction between route unavailable, a failed preview request, and a preview not yet calculated. A server loss during advanced Run simply stops the running indicator and may leave prior results/animation visible. Users cannot know whether retrying or changing backend policy is appropriate.

**Smallest remedy:** Display preview errors and a distinct disconnected/failed-run state; mark old results as belonging to the previous completed run. Include existing backend/configuration context or a diagnostic hint when available, without inventing availability health checks.

**Validation:** Mock no-route, missing-local-backend, and dropped-SSE responses; each yields a visible reason, clears pending state, and offers a defined correction/retry path while preserving clearly identified prior results.

### 9. Browser batch export lacks a browser batch input journey

**Category:** later, unless browser batch processing is a first-release promise. **Severity:** low. **Confidence:** confirmed source surface; design suggestion. **Effort:** M.

**Evidence:** GUI value input is singular (`_serve_ui.py:163,353`); graph requests one scalar value (`:838`); `RunRequest.have` is one dictionary (`serve.py:317–324`) and each run constructs one e1 StrandSet (`:216,253`). The result panel offers CSV/TSV exports (`_serve_ui.py:455–457`) but no batch upload/paste controls were found.

**Impact/reasoning:** A spreadsheet-only biologist with a column of genes must learn CLI input flags and shell redirection to perform the advertised batch workflow; browser downloads cover fan-out rows but not a supplied input batch. This is an interface scope gap, not a claim that batch execution is absent from core.

**Smallest remedy:** For initial scope, explicitly label browser input as one entity and link to the existing batch CLI recipe. Add bounded pasted-column/CSV input later if browser-only batch users are in scope.

**Validation:** Users can find a supported batch route from the browser; if implemented, input-count, per-row outcomes, species broadcast, and export joinability are verified with a mixed deterministic batch.

## Verification log

- Read root AGENTS.md, COMMON.md, assigned prompt; no nested AGENTS.md appeared in the repository file discovery. Read reports 03 and 04 and consulted the earlier-audit context; did not duplicate baseline suites.
- Inspected CLI parser/inspection output code, README entry/batch/Python examples, relevant fetch defaults, server request/payload helpers and adapter, graph projection/card handlers, complete served HTML and targeted JavaScript sections, server tests and relevant view test references. Did not audit every backend or every Python module.
- `.venv/bin/python -c 'import networkx,pytest; print("ready")'` failed at networkx. `command -v node` returned no path. No installed CLI or browser session was run; no dependency installation was attempted.
- Executed a stdlib-only Python AST harness extracting unchanged `_rows`, `_error_list`, CLI/Python artifact helpers and argparse parser functions. The harness supplied placeholder command dispatch functions only to allow parser construction; it did not simulate actual planner/executor execution. Root/weave/keys help rendered (15/36/9 lines respectively). Mixed-result flattening and artifact outputs are recorded in findings 2 and 4.
- Parsed actual TOML specs using tomllib and checked declared single-key reachability for the flagship targets. This bypasses neither planner correctness nor runtime constraints; it is a source declaration inventory only. Specs and Audit 04 corroborate ortholog→gene-ID→UniProt mapping.
- Inspected deterministic and HTTP smoke tests; did not claim they pass. No JavaScript execution, live endpoints, accessibility tools, browser layout/contrast checks, screenshots, credentials, large downloads, or production changes occurred.

## Top five actions

1. Carry and display effective species parameters through every GUI run mode, including traversal prelude (finding 1).
2. Preserve review/outcome/identity/parent metadata in browser results and downloads (finding 2; coordinate with Audit 03 exports).
3. Save/load the active experiment including organism, traversal and expansion; give visible confirmation (finding 3).
4. Make generated CLI/Python examples reproduce supported selected settings and clearly identify placeholders (finding 4).
5. Add keyboard equivalents and proper dialog/label semantics for the main journeys (finding 5).

## Open questions and limitations

- Is the first browser release an exploratory single-entity viewer, or an equivalent interface to CLI experiments? Labeling supported scope reduces confusion while remaining work is scheduled.
- Should the default browser structure journey show a summary list or drill every structure? Either can be useful; users need an explicit cardinality choice and identifier-bearing output.
- Who selects ambiguous candidates, and how is that selection reapplied to a run? The inspected UI does not expose a review flow. First release can at least surface candidate context and a supported recovery command/API pattern.
- Human-readable species lookup would reduce taxid prerequisite knowledge, but requires a product decision and is not needed to repair the current species transport defect.
- Readiness/configuration hints should report available runtime facts, not imply an upstream API was checked merely because an api backend is advertised.
- Actual layout on small displays, floating card overlap, contrast, accessible tree, clipboard permission behavior, and browser downloads need hands-on testing after environment setup. None is certified here. No claims are made about live flagship data coverage.
