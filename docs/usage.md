# Usage

Install → choose a backend → plan → run.

## Install

```bash
uv sync --all-extras
```

## 1. Choose and build a weaver

`taxonweaver` exposes NCBI taxonomy with two interchangeable backends. Build a
weaver with the factory:

```python
from taxonweaver import build_ncbi_weaver

# API only — no local data needed (NCBI Datasets v2, over the network)
weaver = build_ncbi_weaver(enable_api=True)

# Local only — requires a prebuilt SQLite DB (see docs/database.md)
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite")

# Both — local preferred, API as fallback
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite", enable_api=True)
```

The manifest only ever advertises the backends you actually wired in, so a
missing backend never breaks planning — it just isn't an option.

## 2. Register, plan, run

```python
import asyncio
from braidworks.core import (
    BraidRegistry, Braider, LocalExecutor, BackendPolicy, Strand, StrandSet,
)
from taxonweaver import build_ncbi_weaver

async def main():
    registry = BraidRegistry()
    registry.register(build_ncbi_weaver(enable_api=True))

    braid = Braider(registry).plan(
        available_types=frozenset({"organism.name"}),
        target_types=frozenset({"ncbi.taxon.id", "ncbi.taxon.lineage"}),
        backend_policy=BackendPolicy.LOCAL_FIRST,
    )

    sets = [
        StrandSet.from_strands("e1", [Strand("organism.name", "Homo sapiens")]),
        StrandSet.from_strands("e2", [Strand("organism.name", "Mus musculus")]),
    ]

    result = await LocalExecutor(registry).execute(braid, sets)

    for ss in result.resolved:
        print(ss.entity_id, ss.get("ncbi.taxon.id").value)
    for ss, _ in result.unresolved:
        print(ss.entity_id, "no match")

asyncio.run(main())
```

## 3. Read the results

Every input lands in exactly one bucket of `ExecutionResult`:

| Bucket | Meaning |
|---|---|
| `resolved` | Target strands produced; the braid ran to completion |
| `unresolved` | Braid ran but ended in `NO_MATCH` — a valid biological outcome |
| `review_queue` | Ambiguous or review-flagged; a human decision is needed |
| `errors` | Structural failure — missing inputs, backend exhausted |

`len(resolved) + len(unresolved) + len(review_queue) + len(errors)` always equals
the number of inputs.

## Strand types produced by `taxonweaver`

| type_id | group | notes |
|---|---|---|
| `ncbi.taxon.id` | core | matched NCBI tax id |
| `organism.scientific_name` | core | matched scientific name |
| `ncbi.taxon.rank` | core | rank (species, genus, …) |
| `ncbi.taxon.parent_id` | core | immediate parent tax id |
| `ncbi.taxon.match_type` | core | how it matched (exact/synonym/fuzzy/…) |
| `ncbi.taxon.review_required` | core | whether a human should confirm |
| `ncbi.taxon.lineage` | lineage | full ranked lineage (list of `{taxid, rank, name}`) |

Requesting any `core` output computes the whole core group; requesting
`ncbi.taxon.lineage` additionally computes lineage. The cache stores results by
the groups actually computed, so a later `core`-only request is satisfied by a
cached `core`+`lineage` entry.

## Assembling weavers via the factory (optional)

For app-level wiring you can register providers and build by id rather than
calling each `build_*` function directly:

```python
from braidworks.core import WeaverFactory
from taxonweaver import NCBIWeaverProvider

factory = WeaverFactory()
factory.register(NCBIWeaverProvider())
weaver = factory.build("ncbi", {"db_path": "data/ncbi_taxonomy.sqlite"})
```

See [architecture.md](architecture.md) for the two-layer factory rationale and
[database.md](database.md) for building the local DB.
