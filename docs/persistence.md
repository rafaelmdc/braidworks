# Cache lookups and continue saved runs

Braidworks can reuse observations across invocations and save a query's progress.
Both are opt-in and use explicit local SQLite paths. Ordinary queries use an
in-memory lookup cache. Install the required sources before running these commands.

## Choose what to save

| Storage | Purpose | CLI option |
|---|---|---|
| Lookup cache | Reuse observations for matching inputs, parameters, and source identities | `--cache-db PATH` |
| Run store | Keep query state and review decisions so you can continue saved work | `--run-db PATH` |
| Observation archive | Export inputs, outcomes, settings, and references for inspection | `--archive PATH` |

The files are independent. An archive cannot be passed to `resume`, and a cache hit
does not record query progress. Provider databases are a fourth kind of storage;
see [sources](sources.md) for acquisition and [NCBI setup](database.md) for taxonomy.

## Start and inspect a saved query

From the checkout, with UniProt and PDBe installed:

```bash
uv run --no-sync braidworks weave --have protein.query=P04637 \
    --want protein.name,structure.pdb.ids \
    --cache-db data/lookups.sqlite --run-db data/runs.sqlite --run-id p53-structures
uv run --no-sync braidworks runs --run-db data/runs.sqlite
uv run --no-sync braidworks runs p53-structures --run-db data/runs.sqlite --format json
uv run --no-sync braidworks resume p53-structures --run-db data/runs.sqlite --format json
```

Choose a new run ID: existing IDs are never overwritten. If omitted, the generated
ID is printed to stderr. A completed run returns its saved result without new source
calls. Interrupted work continues from saved state; reads interrupted before a wave
is saved may repeat. Resume validates saved settings and declared source identities;
changed identities require a new run. These checks do not freeze a live API dataset.

## Resolve a saved review

Inspect `runs RUN_ID` to get the pending review key and candidate list. Then submit
the decision using that key. For example, **if the reported key is `node:0`**:

```bash
uv run --no-sync braidworks resume RUN_ID --run-db data/runs.sqlite \
    --decision node:0=select:0
```

Candidate indices are zero-based. `KEY=accept` approves a successful observation
that needs review; `KEY=reject` leaves that row unresolved. Repeat `--decision` for
independent items. A decision applies only to that observation; later ambiguous
matches still need review. `--strict` also applies when resuming.

## Use from Python or the browser

The explicit Python query API uses `QueryPersistence`, `execute_managed_query`, and
`continue_run`; a complete script follows below. The `fetch` convenience API does not
accept persistence paths. Browser controls use the same storage options, with paths
on the server's disk. Recipes and generated commands retain those paths; review them
before sharing.

## Create a saved query from Python

With PDBe installed, save this complete script and run it in your environment.
Choose a new `run_id` for each new query; the script closes its weaver when finished.

```python
import asyncio

from braidworks.core import (
    BraidRegistry, QueryPersistence, QueryRequest, Strand, StrandSet,
    execute_managed_query, prepare_query,
)
from pdbe_weaver import build_pdbe_weaver

async def main():
    async with build_pdbe_weaver() as weaver:
        registry = BraidRegistry()
        registry.register(weaver)
        request = QueryRequest(
            inputs=(StrandSet.from_strands(
                "p53", [Strand("protein.uniprot.accession", "P04637")],
            ),),
            targets=frozenset({"structure.pdb.ids"}),
        )
        prepared = prepare_query(registry, request)
        options = QueryPersistence(
            cache_db="data/lookups.sqlite", run_db="data/runs.sqlite",
            run_id="p53-python",
        )
        result = await execute_managed_query(registry, prepared, persistence=options)
        print(result.to_json())

asyncio.run(main())
```

For saved reviews, call `continue_run` with explicit `ReviewDecision` values;
see [the continuation service](../braidworks-core/src/braidworks/core/persistent_query.py).
The managed service renews the lease and retains the last completed checkpoint on
cancellation. An interrupted source read can repeat. See [storage reference](reference/persistence.md)
for ownership, compatibility and retention limits.

## Storage and API reference

[Cache and run-store contracts](reference/persistence.md) describe TTLs, budgets,
leases, revisions, schemas and retention. Persistence remains opt-in. Keep files on
local disk and back up run history you need to retain. Close owners before removing
files; there is no automatic retention policy.
