# Braidworks

Braidworks is a framework for composing biological databases into one network of data resolvers. Each data source is a **Weaver** (UniProt, PDBe, Reactome, QuickGO, STRING, AlphaFold, NCBI taxonomy, BacDive, Disbiome…). You describe what you have and what you want; Braidworks finds the path between them — across all installed weavers — and runs it. Most weavers are keyless public APIs and need no setup.

New here? Start with the [README](../README.md) (biologist-friendly quickstart) or [usage.md](usage.md).

## Start here

Follow the [installation guide](installation.md), then the
[README quickstart](../README.md#for-biologists-the-bare-minimum) for your first
species-pinned query. Continue with [usage](usage.md) for Python, batches and exports.

## Recipes and reference

| Task | Documentation |
|---|---|
| Choose a source and prepare its backend | [Source setup catalogue](sources.md) |
| Read files, tune parameters, export results or fan out | [CLI and Python usage](usage.md) |
| Build the optional NCBI taxonomy database | [Database setup](database.md) |
| Find producers, consumers and routable keys | [Generated key index](keys-index.md) |
| Understand ambiguity and confidence controls | [Core 0.12 migration](migrating-to-0.12.md) |
| See exact command options | braidworks --help; braidworks weave --help; weaverkit --help |

The result buckets are explained below. Source references come from
braidworks references and each weaver's README; software licensing is separate
from biological-data provenance.

## Contributors and maintainers

- [Contributing](../CONTRIBUTING.md) and [AGENTS.md](../AGENTS.md): setup and boundaries.
- [weaverkit](../weaverkit/README.md) and [implementation guide](weaver-implementation-guide.md): spec, scaffold, implementation and strict verification.
- [Architecture](architecture.md), [repository layout](repo-structure.md) and [fan-out model](fanout-roadmap.md): framework contracts and design.
- [Release rehearsal](releasing.md): build and verify distributions before publication.
- [Current work list](NEXT.md) and [weaver roadmap](weaver-roadmap.md): remaining work and proposed sources.

Historical designs: [original MVP plan](implementation-plan.md) and
[local database setup design](local-db-setup-plan.md). These preserve past decisions;
use the user guides above for current operating instructions.

## Concept in One Paragraph

Every piece of data is a typed `Strand`. A collection of strands for one entity is a `StrandSet`. Weavers declare `Capabilities`: what strand types they consume and what they produce. A `BraidRegistry` builds a graph from those declarations. A `Braider` finds the shortest route from your available strand types to your target types. An `Executor` runs the braid in batch, using a `StrandCache` so the same lookup is never repeated. When a weaver is ambiguous or uncertain, the result is flagged for human review rather than silently propagated.

## Quick Example

Cross two keyless databases — UniProt → PDBe — to get a protein's structures:

```python
from braidworks.core import BraidRegistry, Braider, LocalExecutor, Strand, StrandSet
from uniprot_weaver import build_uniprot_weaver
from pdbe_weaver import build_pdbe_weaver

registry = BraidRegistry()
registry.register(build_uniprot_weaver())
registry.register(build_pdbe_weaver())

braid = Braider(registry).plan(
    available_types=frozenset({"protein.query"}),
    target_types=frozenset({"protein.name", "structure.pdb.ids"}),
)

strand_sets = [StrandSet.from_strands("p53", [Strand("protein.query", "P04637")])]
result = await LocalExecutor(registry).execute(braid, strand_sets)

for ss in result.resolved:
    print(ss.get("protein.name").value)       # Cellular tumor antigen p53
    print(ss.get("structure.pdb.ids").value)  # ['9r2q', '9r2m', '8r1f', ...]

for ss, weave_result in result.unresolved:
    print(f"{ss.entity_id}: no match found")
```

See [usage.md](usage.md) for more examples (organism/taxonomy, fan-out, backends).

## Result Buckets

Each terminal entity has one outcome. Fan-out counts children rather than original
inputs. Diagnostics can include recovered failures, so `errors` is not a disjoint
terminal bucket: use `fatal_errors` for errors that prevented completion.

| Bucket | Meaning |
|---|---|
| `resolved` | Target strands were produced; braid ran to completion |
| `unresolved` | Braid ran but ended in `NO_MATCH` — valid biological outcome |
| `review_queue` | Ambiguous result or review flag; human decision needed |
| `fatal_errors` | Terminal failure — missing inputs or exhausted backends |
| `errors` | Diagnostic history, including failures recovered through another route |

Ambiguous resolver results pause for review by default. Explicit automatic selection
retains requires_review; positive confidence floors still apply. See
[migrating-to-0.12.md](migrating-to-0.12.md) for the policy controls,
[usage.md](usage.md) for exports, and [fanout-roadmap.md](fanout-roadmap.md) for bounds.
