# Roadmap: cardinality fan-out (one → many expansion)

**Status:** Phase 1 **shipped** (`braidworks-core` 0.2.0); Phases 2–4 designed, not
built. This is a **core** feature, not a weaver capability. Build it deliberately, in
phases — **the full fan-out mechanism (Phases 1–3) before the run visualizer (Phase 4).**

## Phase 1 — shipped (resolver/entry fan-out)

`ExpandPolicy` (`braidworks.core.ExpandPolicy`, modes `TOP` / `TOP_K(k)` / `ALL`) is
plumbed through `LocalExecutor.execute(..., expand_policy=, max_expansion=)`. On an
`AMBIGUOUS` result **carrying candidates**:

- **`TOP`** (default) — auto-selects the single highest-confidence candidate (ties
  broken by a stable serialization of its strands) and merges it in place; a warning
  records the N→1 collapse so it is never silent. *This changed the previous default*,
  which routed every `AMBIGUOUS` to the review queue.
- **`TOP_K(k)` / `ALL`** — forks the entity into k / all lineage-tagged children, each
  carrying the parent strands plus one candidate's strands; the children re-enter the
  remaining waves and end as independent `resolved` leaves.

`AMBIGUOUS` with **no** candidates is unchanged: there is nothing to pick or fork, so it
still routes to the review queue / RAISE per `ReviewPolicy`. Children carry
`StrandSet.parent_id` (the originating-input id, preserved across forks) for regrouping.
`max_expansion` (default 10 000) caps the per-run leaf count with a logged truncation.
Cache keys already include each child's distinct fan value, so children never collide.

## Why (the principle)

Braidworks exists to **mirror real API capabilities and let them interconnect**. A
huge fraction of those capabilities are intrinsically **one → many**:

- one protein query → **all** UniProt hits that match (not just the top one);
- one accession → **all** pathways it participates in / **all** PDB structures / **all**
  interaction partners;
- one taxon → all its children; one disease → all associated microbes.

Today the model collapses every one→many to a **single representative** at the join
boundary (`uniprot._pick` picks one protein; a join key like `pathway.reactome.id` is
**scalar**, so it can only carry one value to chain onward). The descriptive *data* is
returned as a capped list (`pathway.reactome.names` etc.), but you **cannot chain on
each of the many** — e.g. "for my protein, take every pathway and pull each pathway's
detail" is impossible. **Collapsing to one genuinely blocks real questions**; it is the
single biggest gap against the vision. Fan-out fixes it.

## What it is

A first-class runtime operation: **one entity becomes N, then the braid continues per
child**, governed by a policy knob:

- **`ExpandPolicy`** (sits beside the existing `BackendPolicy` / `ReviewPolicy`):
  - `TOP` — pick the representative, 1 result. **Exactly today's behaviour** (so the
    default is backwards-compatible and nothing existing breaks).
  - `TOP_K(n)` — fork the best *n* (e.g. "top 5 hits").
  - `ALL` — fork every value.
- Settable per-run, and overridable per-step / per-type (e.g. expand proteins `TOP_1`
  but pathways `ALL`).

`ExecutionResult.resolved` then holds the **cross-product of leaf entities** — one query
in → every (protein × pathway × …) row out — each a normal `StrandSet` you can keep
enriching/drilling. Expand *and* contract: `ALL` expands; `TOP`/`TOP_K` contracts.

## Two expansion sites, one mechanism

| Question | Fan dimension | Source today |
|---|---|---|
| query → all matching proteins | the candidate set | resolver `candidates` (already emitted!) |
| protein → all pathways / structures / partners | a produced **id set** | a capability output marked multi-valued |

The first reuses machinery that already exists; the second needs a cardinality flag.

## What already exists to build on

- `braidworks-core/.../records.py`: `ResolverRecord.candidates: list[Candidate]` +
  `MatchStatus.AMBIGUOUS` already model "several possible successors."
- The executor already routes `AMBIGUOUS` somewhere deliberate (review queue / HALT,
  `ReviewPolicy`). Fan-out **generalizes** "AMBIGUOUS → review" into "AMBIGUOUS → expand
  per `ExpandPolicy`."
- "Representative pick" is the implicit `TOP`: `uniprot_weaver._pick`, and every
  satellite's "top-N list + true count" cap. These become the `TOP`/`TOP_K` path.
- `braidworks-arq/.../fanout.py` is **unrelated** (it splits a *batch of inputs* across
  workers for throughput; it does NOT expand one input into many). Don't conflate. They
  compose: batch-parallelism × cardinality-expansion.

## What has to change in core

- **`Capability` / output cardinality.** A produced type is `scalar` (today) or `set`
  (fan-out-able). e.g. `pathway.reactome.id` → `set`. Declared in the manifest/spec.
- **Executor entity-forking** (the hard part). The executor (`executor.py`,
  `_run_chunk`/`_run_step_over`) carries a fixed entity list through dependency waves,
  enriching each in place. Fan-out means: when a step yields a `set` (or resolver
  candidates) under `ALL`/`TOP_K`, **replace that entity with N children** (parent
  strands + one fan value each) and feed all N into the remaining waves. Keep one entity
  under `TOP`.
- **Cache & planner: unaffected.** Each child carries a distinct fan value → distinct
  `compute_cache_key`; the braid *plan* (shape) is identical — expansion is purely
  runtime. (Sanity-check the cache key includes the fan value so children don't collide.)
- **`ExecutionResult`** already a flat `resolved` list — it just gets more rows. Consider
  recording provenance of which input each leaf descended from (a parent/lineage id) so
  callers can group results back by the original query.

## Phases (build in order; each its own PR(s))

**Build the whole fan-out *mechanism* first; the run visualizer comes last** (decided
with the user 2026-06-14). The visualizer reads the *result* of a run, so it should be
built against the **finished** fan/lineage model — not a half-built one. Phases 1→3
complete and surface the mechanism; Phase 4 visualizes it once, with no rework.

1. **`ExpandPolicy` + entry/resolver fan-out.** ✅ **Done** (core 0.2.0). Policy enum
   plumbed through `LocalExecutor.execute`; a resolver returning candidates forks per
   candidate under `TOP_K`/`ALL` (or collapses under `TOP`) instead of only
   HALT-to-review. Reuses `CandidateResult`. Covers "query → all hits." See the
   "Phase 1 — shipped" section above.
2. **Mid-braid `set`-output expansion** (completes the mechanism).
   - **Core mechanism — ✅ Done** (core 0.2.1). `Capability.set_outputs: frozenset[str]`
     declares which produced join keys are one→many (subset of `produces`, default empty
     → backwards-compatible). The executor forks on a set-valued produced strand (a list)
     after merge: `TOP`/`TOP_K(1)` collapse to a representative in place (+warning);
     `TOP_K(k>1)`/`ALL` fork the **cross-product** across every fan dimension into
     children, reusing the Phase-1 lineage scheme (`entity_id` `parent#i`, `parent_id` =
     root) and the `max_expansion` cap. Per-type policy via `execute(..., expand_by_type=
     {type: ExpandPolicy})`. See `executor._expand_set_outputs`; tests in
     `tests/test_fanout_setoutput.py`. **Lineage shape decided:** no change needed — the
     hierarchical `entity_id` already encodes nested fans (`e0#1#3`), and `parent_id`
     gives the root; the visualizer (Phase 4) reconstructs the tree by splitting on `#`.
   - **Satellite conversion — next (PR-B).** Make `reactome_weaver` emit
     `pathway.reactome.id` as the full id set (alongside the existing `…names` list) and
     declare it in `set_outputs` (spec → `vocab.py`). Covers "protein → all pathways, each
     drillable." Then `pdb.id`, etc. Needs weaverkit spec/scaffold support for
     `set_outputs` first.
3. **Surface the mechanism (non-visual).** `ExpandPolicy` in the `weaverkit view` path
   query + CLI knobs; align with `braidworks-arq` so expansion children distribute across
   workers; optionally annotate `set`-valued (fan-able) keys in the static network view.
4. **Run-fanout visualizer** (LAST). Project an actual run's `ExecutionResult` (its
   lineage of leaves) into the existing offline HTML engine as a selectable view — the
   "1 input → N (× M …) leaves" trace. Confirmed design (2026-06-14): input is a
   serialized `ExecutionResult.to_json()` (`weaverkit view --run result.json`); output is
   the **full lineage tree** (input → ops → fan → per-leaf chains), reusing the generic
   `{nodes, edges}` template (`VIEWS` already renders arbitrary graphs — see
   `weaverkit/src/weaverkit/view.py:build_path` + template `VIEWS`). Build only after
   Phase 2 fixes the lineage shape, so nested fans render right and the realized fan
   factor (and, if added to `ExecutionResult`, the `ExpandPolicy`) show faithfully.

## Dependent / folds in

- **UniProt `resolve_mapping` capability** (cross-ref IDs → `pdb.id`, `pathway.reactome.id`,
  `gene.ensembl.id`, `protein.interpro.id`, `protein.pfam.id`, `go.term`, …). Discussed
  2026-06-14. It only becomes *connective* once Phase 2 exists (the cross-ref **sets** fan
  out into future id→data weavers). Until then it would just be descriptive leaf lists.
  Build it **after** Phase 2, as a producer of `set` join keys — that is the
  "two paths to the same place" topology the user wants.

## Open questions — settled for Phase 1 (2026-06-14)

- Default `ExpandPolicy` = `TOP`. ✅ **Settled.** But per the user, `TOP` now
  **auto-picks** the best candidate and continues (it no longer routes `AMBIGUOUS` to
  review). The review path survives only for `AMBIGUOUS` with no candidates.
- Per-type policy map. **Deferred to Phase 2.** Phase 1 takes a single run-level
  `ExpandPolicy`; the per-type map lands with `set`-output expansion.
- Result grouping. ✅ **Yes** — `StrandSet.parent_id` carries the originating-input id.
- Blow-up guardrail. ✅ **Done** — `max_expansion` (default 10 000) per-run cap with a
  logged truncation.

## Open questions for Phase 2

- How a caller asks for a fan dimension: explicit per-type policy map, or inferred from
  requesting a `set` output? Lean explicit (`ExpandPolicy` map keyed by type).
- Cross-product of two `ALL` dimensions reuses the same `max_expansion` cap.
