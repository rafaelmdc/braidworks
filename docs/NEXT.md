# Publication work still to finish

Updated 2026-10-04. This is the current work list; older roadmap dates describe
historical plans, not current release guarantees.

The gene-to-protein bridge already ships: UniProt's `map_to_accession` accepts
`gene.ncbi.id` among its alternative inputs. The interactive server also animates
executing routes. Neither is a new implementation task.

## Release gates

1. Keep `make lint` and `make test` green. Validate built wheels and sdists in a
   fresh environment without workspace source overrides, including entry points,
   bundled fixtures, and optional server dependencies.
2. Check package core-version floors against the APIs they use. Choose and declare
   the intended publication channel before publishing. MIT software licensing is
   now declared separately from upstream data licenses.
3. Rehearse the core 0.12 migration with existing workflows. Ambiguity now pauses
   by default; explicit automatic selection still respects confidence floors. See
   [migrating-to-0.12.md](migrating-to-0.12.md).
4. Rehearse a bounded molecular example against live APIs. Record partial coverage
   and upstream failures; an offline test pass does not establish live availability.
5. Regenerate the weaver/key catalogue and verify documentation examples and links.
   Make setup requirements and the browser's single-input scope explicit.

Core correctness and browser transport/export fixes are under active validation.
Do not describe the checkout as published, fully live-validated, or distributed-safe.

## Follow-up features

GO evidence/completeness, run archives, upstream batching, browser batch input and
HTTP request pacing are implemented. Publishing and durable cache/resume are deferred
for separate design decisions. Disease bridges, extra taxonomy sources and production
distributed deployment need deliberate scope and acceptance criteria.

## Pointers

- Human CLI/API recipes: [usage.md](usage.md)
- Existing weavers and planned sources: [weaver-roadmap.md](weaver-roadmap.md)
- Core contracts: [architecture.md](architecture.md)
- Weaver implementation loop: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- Demo script to rehearse: [demo.sh](demo.sh)

The June 2026 notes reported Reactome detail failures and unauthenticated NCBI rate
limits. Those are historical observations; recheck the endpoints before treating
either as a current limitation.
