# CLI and Python API usage audit

## Executive assessment

The public API has a useful progression: `fetch`/`async_fetch` for simple lookups, explicit registry/planner/executor for control, and direct capability calls for source inspection. JSON outputs and separation of stdout/stderr provide a good base for scripting. First-release readiness is weakened by broken streamed table input, incorrect planning with broadcast constants, silent parameter mistakes, and direct `run` treating source failures as successful shell commands. Spreadsheet and JSON exports also lose important outcome information.

This audit initially lacked make, networkx, and pytest. Make subsequently became available and the parent attempted an authorized workspace sync, but it failed building zipfile-deflate64 because gcc/Python headers were absent. No dependencies were installed by this auditor. Reproductions below execute unchanged CLI/facade/discovery bodies with explicitly substituted registry/planner/executor seams and actual core Strand/Capability/WeaveResult types. They establish the local defects described, **not** successful full graph execution or installed-package certification. Audit 01's execution/serialization defects are referenced rather than repeated.

## Strengths worth preserving

- `cli.py:224` uses JSON and Python's CSV writer, preserving JSON value structure and quoting delimited cells properly; progress and errors use stderr (`cli.py:46`).
- `capability.py:161` validates/defaults/coerces declared parameters, with output-group selection kept separate (`capability.py:184`).
- Numeric shared identifiers canonicalize when constructing a Strand (`strand.py:41`, `keytypes.py:81`); isolated checks confirmed gene ID and taxid strings become integers, while protein query remains a string.
- `fetch.py:111` accepts an explicitly reusable registry; `fetch.py:165` supplies a synchronous wrapper and explicitly documents the async alternative for existing event loops.
- `runner.py:31` presents a narrow typed async extension seam. CLI tests already use deterministic ScriptedWeaver fixtures, and direct backend injection via fixture builders supports network-free source testing.
- `traverse.py:64` explicitly disambiguates named relationships and full capability IDs, avoiding an opaque traversal interface.

Unqualified filenames below refer to `braidworks-core/src/braidworks/core/`.

## Numbered findings

### 1. Header-based stdin is consumed before execution

**Category:** release blocker. **Severity:** high. **Confidence:** confirmed isolated execution. **Effort:** S.

**Evidence:** `cli.py:324` calls `_collect_inputs` to inspect table types; `cli.py:353` calls it again. `_open_input` returns the same stdin stream at `cli.py:124`; `_rows_from_file` requires a header at `cli.py:154`. Traversal also recollects at `cli.py:440`.

**Impact/reproduction:** `printf 'protein.query\nP1\nP2\n' | braidworks weave --in-file - --want protein.name --format json` consumes the table while planning, then fails with `error: - has no header row of type-ids`. The harness fed precisely that stdin and argv to actual `cli.main`; it reproduced SystemExit and empty stdout. TSV stdin is broken independently of route execution; CSV stdin additionally defaults to tabs because delimiter inference uses the path extension.

**Smallest remedy:** Collect inputs once and reuse them for planning and execution/traversal. Provide an explicit input delimiter/format for CSV stdin, or a bounded documented sniffing rule.

**Validation:** Real installed CLI subprocesses reading TSV and CSV stdin, including traversal, produce all rows once; stdout parses and exits correctly.

### 2. Broadcast constants make the planner ignore table columns

**Category:** release blocker. **Severity:** high. **Confidence:** confirmed planner-call reproduction and source reasoning. **Effort:** S.

**Evidence:** `cli.py:320` derives available types only from `--have`/`--in-type`; the table is inspected only when that set is empty (`cli.py:324`). `_collect_inputs` does combine constants and row fields at `cli.py:181`.

**Impact/reproduction:** A CSV containing `protein.query` plus `--have ncbi.taxon.id=9606 --want protein.name` supplies both types to each entity but passes only `{ncbi.taxon.id}` to the planner. The fixture planner spy confirmed that exact call. On a registry whose protein-name route starts from protein.query, this produces a false no-route error or an inappropriate alternative route. Heterogeneous sparse tables also plan from a batch-wide union rather than guaranteeing each row meets the selected route.

**Smallest remedy:** Derive available types from the collected merged inputs; explicitly handle/group rows with different input-type sets rather than assuming the union holds for every entity.

**Validation:** Table+constants and sparse multi-input table cases use each row's actual available types; compare with equivalent explicit StrandSet API inputs.

### 3. Direct `run` hides structural failures and ambiguity

**Category:** release blocker. **Severity:** high. **Confidence:** confirmed isolated execution. **Effort:** S–M.

**Evidence:** `cli.py:535` maps every non-OK status to unresolved. `cli.py:538` emits only values/status; `cli.py:540` fails only with `--strict`. There is no error reporting analogous to weave's `_report_errors` at `cli.py:386`.

**Impact/reproduction:** Inject a weaver returning `WeaveStatus.ERROR` with `errors=('Server error 503',)`, then run `run fake describe --have protein.query=P1 --format json`: return code **0**, JSON `status: unresolved`, stderr only `1 unresolved`, and the 503 disappears. AMBIGUOUS similarly becomes unresolved with no candidates or review distinction. A shell pipeline cannot distinguish source downtime from biological absence. Unsupported backends also raise structural exceptions outside the ValueError-only catch (`cli.py:526`; `dispatch.py:38`).

**Smallest remedy:** Preserve NO_MATCH/AMBIGUOUS/ERROR distinctions, report error diagnostics, and fail on ERROR regardless of strictness. Catch known structural exceptions for clean CLI messages; retain direct-call semantics without forcing auto-planning.

**Validation:** Direct run matrix for OK, NO_MATCH, AMBIGUOUS, ERROR, unconfigured/unknown backend, with and without strict; assert status, stderr and exit code parity with the documented failure contract.

### 4. Parameter targeting accepts mistakes silently

**Category:** release blocker for species-sensitive queries. **Severity:** high. **Confidence:** confirmed isolated mapping/direct-run execution. **Effort:** S–M.

**Evidence:** `_map_params` accepts any scoped capability ID at `cli.py:305` without checking route membership; executor only reads params matching actual invocation IDs (`executor.py:520`). Direct run drops the scope entirely (`cli.py:510`). Bare Python facade params with no declaring step silently disappear (`fetch.py:104`). Native facade scopes pass through unchecked (`fetch.py:97`).

**Impact/reproduction:** The actual `_map_params` maps `other:organism=9606` to `{'other': {'organism': '9606'}}` for a route containing only describe; it is never applied. Direct `run ... --param other:organism=9606` instead applies organism=9606 to describe. `_resolve_params({'organsim':'9606'}, ...)` returns `{}`. For a bare TP53 query this can silently remove species restriction, despite CLI bare unknown names being rejected correctly.

**Smallest remedy:** Validate every supplied name and scope against the effective route/direct capability; reject unknown/unused scopes and unknown bare names consistently across CLI and Python. Traversal mapping must include its resolution prelude as well as final/traversal steps.

**Validation:** Typo and wrong-scope cases fail before backend I/O; valid organism scoping gives identical effective params through run, weave, fetch, async_fetch and traversal.

### 5. Machine exports cannot fully account for outcomes

**Category:** first-release improvement. **Severity:** high for batch coverage. **Confidence:** confirmed formatter execution and source inspection. **Effort:** M.

**Evidence:** CSV/TSV columns omit status (`cli.py:236`), although JSON records contain it (`cli.py:209`). Weave emits resolved/unresolved/review buckets but omits entities appearing only in errors (`cli.py:365`); errors go to stderr. Records exclude completion, warnings, review confidence and source provenance. Normal weave citations are built from the initial braid (`cli.py:375`), rather than executed-result references; Audit 01 finding 8 covers the underlying reroute reference omission.

**Impact/reproduction:** Actual formatter/direct-run output for an ambiguous result is just `entity\tprotein.name\ne1`: its status is absent. Spreadsheet users cannot distinguish missing values, review-needed rows and failures. JSON keeps status for emitted rows, but a fatal row disappears entirely, so joining output back to input cannot provide complete row outcomes. Duplicate one-value-per-line inputs retain duplicate entity IDs (confirmed P1/P1); fan-out descendants can then share lineage labels without a unique source-row key.

**Smallest remedy:** Include status in delimited exports and one terminal outcome per input/leaf in machine outputs, with structured diagnostics and a stable source-row identity. Offer optional structured provenance/references; keep stderr's human diagnostics.

**Validation:** Mixed successful/empty/review/error batch, duplicate rows and fan-out export can be joined back unambiguously; JSON and TSV report the same coverage and statuses. Verify rerouted source attribution.

### 6. `--only` does not isolate imports of excluded weavers

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed isolated discovery execution. **Effort:** S.

**Evidence:** `discovery.py:24` loads an entry point before yielding its name; filtering happens later at `discovery.py:38`.

**Impact/reproduction:** With an excluded entry point whose load raises `ImportError('excluded optional dependency missing')`, actual discovery with `only=frozenset({'fake'})` still raises that ImportError. A broken optional plugin can prevent every CLI command, including inspection of a healthy selected weaver; the filter promised for restricted workers also cannot avoid irrelevant import dependencies.

**Smallest remedy:** Filter entry-point metadata before `ep.load()`. Decide separately whether unfiltered inspection should report unavailable weavers rather than abort.

**Validation:** An excluded broken entry point is never loaded; an included broken entry point reports a useful error; selected entry points still register and validate normally.

### 7. Traversal and ordinary weave disagree on nonfatal branch errors

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed source behavior; full traversal execution unverified. **Effort:** S.

**Evidence:** Ordinary weave uses `result.fatal_errors()` (`cli.py:390`); traversal fails on **any** `result.errors` (`cli.py:480`). `run_traversed` carries errors from all phases (`traverse.py:203`). `docs/usage.md:69` describes partial branch failures as nonfatal.

**Impact/reasoning:** Adding `--for-each` can change a partial-success command from exit 0 to exit 1 even when each entity produced usable targets or rerouted. Scripts cannot share a single success policy across these otherwise symmetric interfaces. Audit 01 finding 4 additionally means error fatality needs stable serialization semantics.

**Smallest remedy:** Use one explicit failure-policy helper for weave and traversal, after repairing the underlying fatality identity defect; keep strict review/absence policy separate.

**Validation:** Same partial-success/recovered-error fixture through ordinary weave and traversal yields consistent exit status and diagnostics, including serialized result parity.

### 8. FetchResult lacks the promised public serialization boundary

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed class inspection/isolated instantiation. **Effort:** S.

**Evidence:** `fetch.py:39` exposes a public dataclass with get/column but no to_json/from_json; it is re-exported by `braidworks/__init__.py:8` and `core/__init__.py:36`. Root `AGENTS.md` requires public dataclasses to round-trip. Other result/reference types provide explicit methods (`result.py:73`, `references.py:52`).

**Impact/reproduction:** `hasattr(FetchResult(), 'to_json')` and `hasattr(..., 'from_json')` are both False. Calling code must invent serialization of nested references/errors, or move down to executor results, defeating the shortest supported API path when persisting a batch or crossing an application boundary.

**Smallest remedy:** Add explicit methods composing nested public serializers; preserve plain values and declared order/duplicate-collapse behavior.

**Validation:** Actual JSON encode/decode round trip covers partial values, references and errors and matches executor outcome semantics.

## Verification log

- Read AGENTS.md, COMMON.md and assigned prompt; no nested AGENTS.md was found. Read CLI, public initializers, discovery, runner, fetch, traverse, usage/core README and relevant root README examples; inspected dispatch/capability/strand/result/keytypes, relevant executor portions, test_cli/test_fetch/helpers and representative package factories/API client construction. Did not audit every backend.
- Read reports 01/02 and reused their cache, ambiguity, expansion, serialization and reroute-attribution findings without duplicate workspace tests.
- Initially `command -v make` yielded nothing; system Python 3.14.3 reported networkx=False, pytest=False, httpx=True. Make later appeared at `/usr/bin/make`. Parent reported sync failed building zipfile-deflate64; `.venv/bin/python -c 'import networkx, pytest'` still failed at networkx and `.venv/bin/braidworks --help` was absent at the attempted check.
- `python /tmp/audit03.py` executed unchanged AST-loaded CLI/fetch/discovery modules with core imports omitted only to avoid dependency-heavy public initialization. Actual Strand/Capability/WeaveResult types came from the source. Registry/planner/executor and discovery entry points were explicitly fixture substitutes. Parser help and JSON weaver inspection succeeded; stdin, planner-input, ERROR/AMBIGUOUS, scope, export, duplicate-value, canonicalization and serialization checks produced the results recorded above. First harness attempt used nonexistent StrandSet.add; corrected to add_strand and reran successfully. No production code was altered.
- A strict partial-target seam check returned 0 with only protein.name when protein.length was also requested. This matches current executor's intentional **any target** classification (`executor.py:486`); it is not evidence of a separate unintended defect. There is no present CLI guarantee of complete requested-field coverage.
- A synthetic fetch result placed a partial value in unresolved and the facade dropped it; because actual executor classifies any-target survivors as resolved, this alone is **not** an established normal-path defect and is not promoted to a finding.
- Full installed help/inspection commands, real planner/executor fixture workflows, targeted pytest, flagship live results and repeated-client lifecycle were not verified in the initial environment. No live APIs, downloads, credentials, dependency installs, commits or external messages were performed by this auditor.

## Top five actions

1. Collect table input once and derive planning types from merged rows (findings 1–2).
2. Preserve direct-run errors/review outcomes and return trustworthy exit statuses (finding 3).
3. Reject unused names/scopes consistently before species-sensitive queries (finding 4).
4. Include complete row outcomes and status in machine/spreadsheet exports (finding 5).
5. Apply discovery filters before importing excluded packages (finding 6).

## Open questions and limitations

- Should strictness mean “no entirely absent/review inputs” (current behavior) or “every requested target present”? Keep current partial enrichment useful, but expose missing targets/completion for users who require complete rows; a new policy would be a design suggestion, not a silent semantic change.
- Reusable API weavers retain lazily created httpx.AsyncClient instances (`weavers/uniprot_weaver/src/uniprot_weaver/backends/api.py:193`) and the sync facade makes a fresh event loop per call (`fetch.py:188`). No public close/context lifecycle was found in the inspected interfaces. Repeated sync fetch with a reused live registry may reuse clients across closed loops; this needs a targeted transport/pooling reproduction before calling it a confirmed defect.
- Most inspected keyless factories ignore supplied `**_config` (e.g. `weavers/uniprot_weaver/src/uniprot_weaver/factory.py:25`). Fixture builders support deterministic calls, but configured transport/client ownership needs an explicit supported pattern. No claim is made that every package has the same limitation.
- Native capability IDs are not uniformly namespaced: UniProt uses resolve_protein; NCBI uses ncbi.list_orthologs. CLI inspection can show repeated prefixes. Validate collision assumptions before promising global scoped IDs.
- Static source declarations connect protein.query→UniProt accession→GO processes/interaction partners; accession→pdb.id→structure descriptions; and explicit ncbi.list_orthologs→gene.ncbi.id→UniProt mapping→protein annotations. These are declared routes, not live truth checks. Full installed planning and fixtures remain required; Audit 01 flags traversal stale-attribute and fan-out/review hazards on these workflows.
- Machine JSON schemas have no explicit schema-version marker in inspected CLI/facade output. Before promising compatibility, decide which fields/exit semantics are stable and add consumer-facing contract tests; absence alone is not listed as a defect.
