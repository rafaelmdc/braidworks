# Architecture and correctness audit

## Executive assessment

The framework has credible boundaries and should be repaired incrementally, not rewritten. Shared dispatch and record mapping, pure planning, and the step-runner seam substantially reduce source-specific orchestration. However, release readiness is limited by several ways to return plausible but incorrect or incomplete results: false cache hits, stale traversal attributes, lost review state, and JSON-dependent error classification. Fan-out bounds also do not bound allocation. Distributed execution reuses local orchestration well, but its cache fingerprint and rate-budget claims need qualification.

This was a bounded source audit, not full execution certification. Two focused standard-library reproductions confirmed cache and serialization defects. The checkout initially had no `.venv`; system Python lacked `networkx` and `pytest`, so normal targeted pytest execution was unavailable during this audit. No dependencies were installed and no production files were changed.

## Strengths worth preserving

- `runner.py:31` defines a small transport-neutral batch seam; `braidworks-arq/src/braidworks_arq/executor.py:34` reuses `LocalExecutor`, avoiding divergent distributed fallback/review orchestration.
- `registry.py:84` validates manifests before registration; its multigraph preserves alternative sources, and `planner.py:42` deterministically chooses between parallel edges by cost and IDs.
- `executor.py:599` distinguishes configuration failures from unavailable backends, and `executor.py:610` applies per-entity status fallback rather than re-resolving successful inputs.
- Effective parameters are resolved before cache construction (`executor.py:520`), and consumed values, backend, version, and effective parameters contribute to cache identity (`cache.py:42`). Upstream provenance deliberately does not fragment equivalent cache inputs.
- Candidate ranking is explicit and stable (`executor.py:943`), and fan-out root lineage survives successive forks (`executor.py:812`, `strand.py:137`).
- Backend records and mappers are domain-neutral dictionaries keyed by declared types. The shared-key normalization table is an explicitly documented vocabulary exception, not evidence of biological execution logic leaking into core.

Paths below are relative to the repository; unqualified core filenames live under `braidworks-core/src/braidworks/core/`.

## Numbered findings

### 1. Always-computed groups can cause false cache hits with missing output

**Category:** release blocker. **Severity:** high. **Confidence:** confirmed by isolated execution. **Effort:** S–M.

**Evidence:** `mapper.py:26` unions `always_computed_groups` into cache coverage; `mapper.py:49`, `mapper.py:62`, `mapper.py:100`, and `mapper.py:114` emit only externally triggered group strands. `cache.py:96` trusts group coverage. Real manifests use this combination: `weavers/uniprot_weaver/src/uniprot_weaver/vocab.py:81` declares always-computed identity while function/taxonomy are separate groups.

**Impact/reproduction:** For a capability with identity `{id}` and detail `{description}`, always-computed identity, and a record containing both values, request only detail and cache the mapped result. It advertises `{'identity','detail'}` but contains only description. A later identity request hits this entry and never obtains id. The isolated run printed `identity cache hit: True id emitted: False`. Cached and uncached calls can therefore differ observably and block downstream joins.

**Smallest remedy:** Make advertised cache group coverage match emitted data, either emitting the internally computed groups' available strands or excluding groups whose values are absent. Decide how optional `None` attributes affect group fulfillment explicitly.

**Validation:** Run detail→identity and identity→detail with a shared cache against real UniProt-shaped fixtures and compare to fresh-cache executions, including downstream accession consumers.

### 2. Traversal retains stale seed attributes when the join key is already present

**Category:** release blocker. **Severity:** high. **Confidence:** confirmed by source reasoning; end-to-end reproduction needs dependencies. **Effort:** S–M.

**Evidence:** `traverse.py:154` only runs the resolution prelude if the source key is absent from the batch union. The seed-strand restriction at `traverse.py:170` occurs only inside that prelude. Directly supplied inputs instead enter the fan with all attributes (`traverse.py:176`); children clone all strands (`strand.py:143`), and final planning skips targets already available (`planner.py:88`).

**Impact/reproduction:** Start `run_traversed` with gene ID 7157 and `gene.symbol='TP53'`, traverse orthologs producing other gene IDs, and request gene.symbol. Children inherit TP53; final planning considers their target satisfied and does not describe the orthologs. This contaminates the NCBI ortholog flagship workflow when seed inputs contain annotations. Successive traversals can similarly retain attributes from the previous entity.

**Smallest remedy:** Restrict to the traversal's join key immediately before every traversal, independent of whether a prelude was needed, preserving lineage and explicit context separately.

**Validation:** Existing join key plus seed attributes; two consecutive relationships; mixed inputs with and without source keys. Verify child attributes come from child IDs and each child's root lineage remains intact.

### 3. Ambiguous candidate expansion ignores review and confidence safeguards

**Category:** release blocker pending explicit policy decision. **Severity:** high. **Confidence:** confirmed source behavior. **Effort:** M.

**Evidence:** `executor.py:723` expands candidates before examining `ReviewPolicy`, while threshold checks only apply to OK at `executor.py:735`. Candidate merging (`executor.py:794`, `executor.py:815`) never propagates the ambiguous result's `requires_review`. `mapper.py:119` marks ambiguity for review; public `ReviewPolicy` documentation at `executor.py:88` still says ambiguity always halts/raises. `docs/fanout-roadmap.md:10` explicitly documents the changed default auto-selection: this is a deliberate expansion feature, not an accidental discovery of auto-selection itself.

**Impact/reproduction:** An AMBIGUOUS result with low-confidence candidates resolves under default TOP, even with `review_policy=RAISE` and a high confidence threshold. The selected StrandSet has `requires_review=False`; one candidate produces no collapse warning. A caller cannot rely on explicit RAISE or persisted review flags to prevent uncertain biological mappings.

**Smallest remedy:** Define precedence between cardinality selection and review policies. At minimum honor explicit RAISE, apply threshold to selected candidates, and retain `requires_review` on accepted/forked uncertain entities. Update contradictory public contracts deliberately.

**Validation:** Matrix of TOP/TOP_K/ALL × HALT/ALLOW_CONTINUE/RAISE, one versus multiple candidates, threshold above candidate confidence, and cache-hit parity. Do not weaken conformance checks merely to endorse the current behavior.

### 4. Partial-success errors become fatal after JSON round trip; totals double-count entities

**Category:** release blocker for serialized results. **Severity:** high. **Confidence:** confirmed by isolated execution. **Effort:** S–M.

**Evidence:** `executor.py:193` associates resolved entities with errors using Python object identity. `executor.py:213` and `executor.py:221` independently deserialize each bucket. `executor.py:180` sums all bucket lengths despite branch-local errors also being retained for resolved entities (`executor.py:488`).

**Impact/reproduction:** Construct one StrandSet, add it to resolved and as an unrecovered branch error, round-trip `ExecutionResult` through actual JSON. `fatal_errors()` changes from 0 to 1. `total()` reports 2 for that single entity. Persisted/worker-facing results can produce different exit/status decisions and misleading coverage counts.

**Smallest remedy:** Separate entity outcome from branch diagnostics, or associate them through a stable execution/entity identifier. Define whether total counts entities, leaves, or diagnostic records; avoid relying on object aliasing in a JSON API.

**Validation:** Extend the existing partial-success test with complete `ExecutionResult` serialization and assert stable fatality and correct unique entity/leaf counts. Include duplicate caller entity IDs when choosing an identity scheme.

### 5. Fan-out cap runs after allocation and silently loses leaves from result accounting

**Category:** release blocker for advertised bounded fan-out. **Severity:** high. **Confidence:** confirmed source behavior; large allocation not exercised. **Effort:** M.

**Evidence:** `executor.py:895` fully constructs each dimension's cross-product before `executor.py:915` stores all spawned children. Only later does `executor.py:469` enforce `max_expansion` by slicing; discarded children only generate a logger warning. `executor.py:300` applies this independently per input chunk. `docs/fanout-roadmap.md:23` describes a per-run leaf cap.

**Impact/reproduction:** Two ALL dimensions of 1,000 values allocate approximately one million descendants before a configured cap of 10 can help. Multiple input chunks each admit their own cap, so per-run output may exceed it. Truncated parents/leaves have no result-level warning or terminal outcome, making downstream spreadsheet coverage indistinguishable from complete output.

**Smallest remedy:** Generate bounded children lazily under a shared run budget; report truncation in serialized execution metadata including counts and affected roots. Explicitly define per-root versus per-run semantics.

**Validation:** Count `clone` invocations for a modest cross-product with cap 10; test several chunks; verify bounded allocation, deterministic retained order, lineage, and visible truncation without large memory experiments.

### 6. Backend policy is applied after choosing the cheapest route

**Category:** first-release improvement (blocker if LOCAL_ONLY is marketed as exhaustive planning). **Severity:** medium. **Confidence:** confirmed source reasoning. **Effort:** S–M.

**Evidence:** `planner.py:90` routes against the unfiltered registry graph; `planner.py:92` selects the cheapest parallel capability. `planner.py:186` applies backend policy only when constructing already-selected invocations.

**Impact/reproduction:** Register cheap API-only A→B and a more expensive local-only A→B. Request LOCAL_ONLY. The planner chooses the API capability and raises NoPlanError even though a valid local braid exists. A cheaper API-only intermediate path similarly hides a valid local route.

**Smallest remedy:** Prune graph capabilities whose backends do not intersect policy before Dijkstra, then retain existing assignment logic.

**Validation:** Parallel-edge and multi-hop cases with disallowed cheapest paths and allowed alternate paths; preserve exclusion/reroute behavior.

### 7. Batch cardinality violations are silently truncated or can misassociate entities

**Category:** first-release improvement. **Severity:** high. **Confidence:** confirmed source reasoning. **Effort:** S.

**Evidence:** Shared dispatch maps however many records a backend returns (`dispatch.py:91`); `_call_batch` appends results without checking the sub-batch length (`executor.py:643`). Both `_resolve_misses` (`executor.py:610`) and result application (`executor.py:550`) use truncating zip; `_resolve_misses` removes None results (`executor.py:624`).

**Impact/reproduction:** If a custom/buggy backend returns fewer results than inputs, trailing inputs may become synthetic unresolved outcomes; across sub-batches, later responses can shift onto earlier entities. Conformance tests promise one ordered result per input but production execution does not guard the seam. A schema-drift/backend error can thus masquerade as valid biological absence or attach another query's result.

**Smallest remedy:** Check exact result cardinality per runner sub-batch and dispatch record batch, raising a structural contract error. For shared records, optionally validate echoed queries before mapping; do not invent alignment for arbitrary custom results.

**Validation:** Too few/too many responses in the first and later chunks, ensuring no cache pollution or cross-entity merges; keep existing conformance tests unchanged.

### 8. Successful reroutes omit alternate source references

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed source reasoning. **Effort:** S.

**Evidence:** Initial references are derived from the original plan at `executor.py:272`. `_reroute` executes a new braid (`executor.py:369`) and copies its data/error buckets (`executor.py:372`–`375`) without merging `sub.references`.

**Impact/reproduction:** Direct source A fails; alternate source B resolves the target. Final strands identify B, but result bibliography only credits the original plan. Attribution-required upstream data may lack its source citation in exported results. This concerns upstream data provenance, not the repository's software license.

**Smallest remedy:** Union sub-result references into the parent, deduplicating stably by weaver ID as traversal already does.

**Validation:** Existing reroute test with distinct provenance on original and alternate sources; assert the successful source is cited and references survive JSON.

### 9. Cluster budget undercharges oversized batches and does not measure actual HTTP calls

**Category:** first-release improvement; release blocker for the unqualified claim of safe upstream rate limiting. **Severity:** high. **Confidence:** confirmed arithmetic/source behavior, no Redis/live load test. **Effort:** M.

**Evidence:** `braidworks-arq/src/braidworks_arq/tasks.py:85` charges batch length, but `ratelimit.py:30` clamps charge to capacity; `tasks.py:59` makes capacity approximately one second's rate. `weavers/pdbe_weaver/src/pdbe_weaver/backends/api.py:139` illustrates serial per-query calls. The architecture document itself discusses per-call gating as planned work at `docs/architecture.md:550`.

**Impact/reproduction:** With rate 3 and 100 single-ID queries in one task, only 3 tokens are charged before all calls run. Multiple workers can under-account independently. Conversely a true 1-request batch is overcharged by entity count. A per-entity operation requiring multiple HTTP calls can exceed budget even when worker chunks contain one entity. The current limiter bounds estimates, not actual external-call rate.

**Smallest remedy:** Until per-call gating exists, document the estimate limitation and constrain task batch size for budgeted single-ID backends without defeating bulk APIs. Add an explicit accounting seam for actual requests; do not simultaneously charge task and request layers. Reject non-positive/non-finite rates rather than accepting them in `ratelimit.py:109`.

**Validation:** More-than-capacity cost tests, true bulk versus single-ID/multi-call backends, and a small Redis-backed clock-controlled test proving cluster request rate rather than merely token arithmetic.

### 10. Distributed cache identity uses the orchestrator's data fingerprint, not the worker's

**Category:** first-release improvement. **Severity:** high for heterogeneous local workers. **Confidence:** inferred deployment risk from confirmed protocol omission. **Effort:** M.

**Evidence:** `executor.py:518` reads the local registry fingerprint for lookup and `executor.py:561` reads it again for storage. `braidworks-arq/src/braidworks_arq/tasks.py:80` selects the worker's independently constructed weaver. The task returns only WeaveResult JSON (`tasks.py:102`), which contains version/backend but no source fingerprint; the runner forwards only those results (`runner.py:112`).

**Impact/reproduction:** Orchestrator configured with local dataset A dispatches to a worker using dataset B. Results from B can be cached as A; replacing worker B's data does not invalidate the orchestrator cache. Correctness requires an undocumented homogeneous registry/data assumption across processes.

**Smallest remedy:** Establish a version/fingerprint handshake or include worker fingerprint in a transport envelope, verify expected identity before dispatch/cache reuse, and document homogeneous fleet requirements until supported. Re-reading a mutable local fingerprint after execution also deserves an explicit snapshot contract.

**Validation:** Inline worker/orchestrator registries with different fingerprints; reject mismatches or key results with verified worker identity; test dataset updates without manual cache clearing.

## Verification log

- Read root `AGENTS.md`, `.audit-local/COMMON.md`, and assigned prompt. `rg --files -g AGENTS.md` found no nested instruction files.
- Read targeted core modules: planner, registry, executor, traverse, runner, cache, dispatch, records, mapper, strand, capability, braid, references, discovery, keytypes; inspected architecture/fan-out docs and representative UniProt manifest and PDBe HTTP batch implementation. Inspected relevant executor, fan-out, traversal, rate-limit, and error-tolerance tests. Did not audit every weaver.
- `python3 -c 'import sys, networkx; ...'` failed with `ModuleNotFoundError: networkx`; no root `.venv/bin/python` existed. Did not run pytest or a duplicate workspace suite.
- Focused mapper/cache reproduction ran with standard Python by constructing namespace packages pointing at actual core source, bypassing only the dependency-heavy public initializer. No mapping/cache code was copied or modified. Output: `groups: ['detail', 'identity']`; `emitted: ['description']`; `identity cache hit: True id emitted: False`.
- Focused serialization reproduction compiled the unchanged AST class definitions for `ExecutionError` and `ExecutionResult`, importing actual StrandSet/result/reference types. Initial compile attempt missed AST line locations; corrected with `ast.fix_missing_locations`. Output after actual `json.dumps`/`loads`: `fatal errors before / after JSON: 0 1`; `one entity total(): 2`. This isolates dataclass behavior, not whole executor execution.
- `git show braidworks-core-v0.4.0:.../runner.py` and executor source confirmed the arq dependency floor already includes the runner seam, params, and cardinality hooks. No unsupported-floor finding was inferred from today's version alone. An installed old-core compatibility test remains unrun.
- No live APIs, Redis service, credentials, data downloads, or dependency installs. Only this report was written.

## Top five actions

1. Repair cache coverage versus emitted strands (finding 1); add real grouped-output cache parity cases.
2. Remove seed attribute carryover on every traversal (finding 2).
3. Specify and enforce ambiguity/review/threshold precedence, retaining review state (finding 3).
4. Make result outcome/error accounting invariant under serialization (finding 4).
5. Apply expansion limits before cloning and expose truncation to callers (finding 5).

## Open questions and limitations

- Is default ambiguous auto-selection a deliberate public-release guarantee? Fan-out docs say yes; architecture and ReviewPolicy docs say no. Policy needs one deliberate reviewed decision, especially explicit RAISE and threshold semantics.
- Does max_expansion mean run leaves, per-root leaves, or live working population? Current implementation behaves like a per-chunk live population cap and does not bound materialization.
- Are distributed local datasets guaranteed identical across workers and orchestrators? The protocol does not verify this. No deployment reproduction was run.
- Existing source declarations support protein.query→UniProt accession→QuickGO biological processes / STRING partners, accession→PDBe pdb.id→structure descriptions, and gene.ncbi.id→UniProt mapping→annotations. NCBI orthologs require explicit traversal because they reproduce gene.ncbi.id. This reachability assessment uses current manifests/index and graph rules, not executed API or installed-entry-point planning. Spreadsheet/CLI behavior is another audit's scope.
- Equal-cost parallel source choice is deterministic, but route choice across different equally priced source types uses frozenset/set iteration (`planner.py:158`, `registry.py:139`); cross-process reproducibility needs a targeted hash-seed test before asserting a defect. No such test was run.
- Fallback results are stored under the actual fallback backend but subsequent lookup only checks the primary (`executor.py:531`); repeated primary failure can re-run an otherwise cached fallback. This is an efficiency/test opportunity, not included as a separate release finding.
- `ArqStepRunner` lazily owns a Redis pool but exposes no close/context lifecycle (`runner.py:43`–`50`); representative API clients similarly have long-lived ownership. Define lifecycle when library-created executors/registries are used repeatedly. This was not leak-tested and is not counted as a confirmed leak.
- Structural batch checks, policy filtering, and cache coverage corrections are small seams suitable for incremental work. Do not split the executor merely because of its size; preserve unified orchestration and add targeted observable behavior tests.
