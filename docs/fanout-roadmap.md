# Roadmap: cardinality fan-out (one → many expansion)

**Status:** designed, not built (planned with the user 2026-06-14). This is a
**core** feature, not a weaver capability. Build it deliberately, in phases.

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

1. **`ExpandPolicy` + entry/resolver fan-out.** Add the policy enum + plumb it through
   `LocalExecutor.execute`. When a resolver returns multiple candidates (or AMBIGUOUS),
   fork per candidate under `TOP_K`/`ALL` instead of only HALT-to-review. Smallest slice,
   reuses `Candidate`. Covers "query → all hits."
2. **Mid-braid `set`-output expansion.** Add output cardinality to `Capability`; teach
   the executor to fork on a `set`-valued produced join key. Convert the satellites to
   emit their id sets (`pathway.reactome.id`, `pdb.id`, …) as fan dimensions (alongside
   the existing descriptive lists). Covers "protein → all pathways, each drillable."
3. **Surface it.** `ExpandPolicy` in the `weaverkit view` path query + CLI; align with
   `braidworks-arq` so expansion children distribute across workers; show fan dimensions
   in the network view.

## Dependent / folds in

- **UniProt `resolve_mapping` capability** (cross-ref IDs → `pdb.id`, `pathway.reactome.id`,
  `gene.ensembl.id`, `protein.interpro.id`, `protein.pfam.id`, `go.term`, …). Discussed
  2026-06-14. It only becomes *connective* once Phase 2 exists (the cross-ref **sets** fan
  out into future id→data weavers). Until then it would just be descriptive leaf lists.
  Build it **after** Phase 2, as a producer of `set` join keys — that is the
  "two paths to the same place" topology the user wants.

## Open questions to settle before Phase 1

- Default `ExpandPolicy` = `TOP` (backwards-compatible) — confirm.
- How a caller asks for a fan dimension: explicit per-type policy map, or inferred from
  requesting a `set` output? Lean explicit (`ExpandPolicy` map keyed by type).
- Result grouping: do leaves carry a lineage/parent id so callers regroup by input?
  (Recommended yes.)
- Guardrails against blow-up (cross-product of two `ALL` dimensions): a per-run cap +
  a logged truncation, mirroring the "no silent caps" rule.
