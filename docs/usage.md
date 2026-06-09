# Usage

Install → choose a backend → plan → run.

## Install

```bash
uv sync --all-extras
```

## 1. Choose and build a weaver

`taxon_weaver` exposes NCBI taxonomy with two interchangeable backends. Build a
weaver with the factory:

```python
from taxon_weaver import build_ncbi_weaver

# API only — no local data needed (NCBI Datasets v2, over the network)
weaver = build_ncbi_weaver(enable_api=True)

# Local only — explicit prebuilt SQLite DB
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite")

# Local with automatic setup — builds/reuses the DB in the per-user cache.
# On a terminal it prompts before the ~70 MB download + ~1 min build; otherwise
# it honors auto_setup / BRAIDWORKS_AUTO_DOWNLOAD or raises an actionable error.
weaver = build_ncbi_weaver(auto_setup=True)

# Both — local preferred, API as fallback
weaver = build_ncbi_weaver(db_path="data/ncbi_taxonomy.sqlite", enable_api=True)
```

The manifest only ever advertises the backends you actually wired in, so a
missing backend never breaks planning — it just isn't an option.

### One-time local DB setup from the CLI

The recommended way to provision the local database once:

```bash
taxon-weaver ensure              # prompt, then download + build into the user cache
taxon-weaver ensure --yes        # non-interactive (CI/servers)
taxon-weaver ensure --refresh    # rebuild from the latest NCBI taxdump
```

`ensure` is idempotent (a valid DB is reused instantly) and, when the DB is
already present, reports whether a newer NCBI release is available. The DB lands
in the per-user cache by default (override with `--db` or `BRAIDWORKS_DATA_DIR`),
so `build_ncbi_weaver(auto_setup=True)` finds it automatically afterward.

## 2. Register, plan, run

```python
import asyncio
from braidworks.core import (
    BraidRegistry, Braider, LocalExecutor, BackendPolicy, Strand, StrandSet,
)
from taxon_weaver import build_ncbi_weaver

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

## Strand types produced by `taxon_weaver`

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
from taxon_weaver import NCBIWeaverProvider

factory = WeaverFactory()
factory.register(NCBIWeaverProvider())
weaver = factory.build("ncbi", {"db_path": "data/ncbi_taxonomy.sqlite"})
```

See [architecture.md](architecture.md) for the two-layer factory rationale and
[database.md](database.md) for building the local DB.
