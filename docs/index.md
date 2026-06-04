# Braidworks

Braidworks is the framework that turns TaxonWeaver into one node in a composable network of biological data resolvers. Each resolver is a **Weaver**. You describe what you have and what you want; Braidworks finds the path between them and runs it.

## Documents

- [Usage](usage.md) — Install, choose a backend, plan, and run.
- [Database](database.md) — Build / acquire the NCBI taxonomy DB for the local backend.
- [Architecture](architecture.md) — Core abstractions, contracts, data flow, and design decisions.
- [Repository Structure](repo-structure.md) — Full repository layout.
- [Implementation Plan](implementation-plan.md) — Concrete build order, deliverables, and definition of done for the MVP.
- [Contributing](../CONTRIBUTING.md) — Dev setup, testing, and how to add a new weaver.

## Concept in One Paragraph

Every piece of data is a typed `Strand`. A collection of strands for one entity is a `StrandSet`. Weavers declare `Capabilities`: what strand types they consume and what they produce. A `BraidRegistry` builds a graph from those declarations. A `Braider` finds the shortest route from your available strand types to your target types. An `Executor` runs the braid in batch, using a `StrandCache` so the same lookup is never repeated. When a weaver is ambiguous or uncertain, the result is flagged for human review rather than silently propagated.

## Quick Example

```python
from braidworks.core import (
    BraidRegistry, Braider, LocalExecutor, BackendPolicy, Strand, StrandSet,
)
from taxonweaver import build_ncbi_weaver

registry = BraidRegistry()
# API backend needs no local data; pass db_path=... to add the local backend.
registry.register(build_ncbi_weaver(enable_api=True))

braider = Braider(registry)
executor = LocalExecutor(registry)

strand_sets = [
    StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")]),
    StrandSet.from_strands("e2", [Strand("organism.name", "Mus musculus")]),
]

braid = braider.plan(
    available_types=frozenset({"organism.name"}),
    target_types=frozenset({"ncbi.taxon.id", "ncbi.taxon.lineage"}),
    backend_policy=BackendPolicy.LOCAL_FIRST,
)

result = await executor.execute(braid, strand_sets)

for ss in result.resolved:
    taxid = ss.get("ncbi.taxon.id")
    lineage = ss.get("ncbi.taxon.lineage")

for ss, weave_result in result.unresolved:
    print(f"{ss.entity_id}: no match found")
```

See [usage.md](usage.md) for the full runnable example and backend options.

## Result Buckets

Every entity lands in exactly one bucket:

| Bucket | Meaning |
|---|---|
| `resolved` | Target strands were produced; braid ran to completion |
| `unresolved` | Braid ran but ended in `NO_MATCH` — valid biological outcome |
| `review_queue` | Ambiguous result or review flag; human decision needed |
| `errors` | Structural failure — missing inputs, backend exhausted |
