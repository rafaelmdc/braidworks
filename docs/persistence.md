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
`continue_run`; reference details follow below. The `fetch` convenience API does not
accept persistence paths. Browser controls use the same storage options, with paths
on the server's disk. Recipes and generated commands retain those paths; review them
before sharing.

## Storage and API reference

The following details are for applications configuring storage policies, ownership,
and retention. They are separate from the steps needed for an ordinary saved query.

### Lookup cache

```python
from braidworks.core import CachePolicy, SQLiteStrandCache

cache = SQLiteStrandCache(
    "data/lookups.sqlite",
    policy=CachePolicy(
        positive_ttl=3600, negative_ttl=300,
        max_payload_bytes=256 * 1024 * 1024,
    ),
)
```

Pass `cache` to `execute_query` or an explicit executor. CLI equivalents are
`--cache-positive-ttl`, `--cache-negative-ttl`, and `--cache-max-bytes`, with the
same defaults shown above.

The default executor still uses memory. Cache keys include effective parameters,
weaver/backend/source identity and input values; group coverage is checked separately.
Ambiguous cached observations preserve review requirements. Errors are not cached.
A zero TTL disables that category. Expiry is evaluated when reading; writes clean up
expired rows and evict oldest payloads to fit the configured budget. Payload bytes
exclude SQLite pages, indexes and WAL; ordinary deletion reuses pages rather than
shrinking the file. For explicit physical reclamation when no executions use the file,
SQLite checkpoint/VACUUM operations are an administrative choice, not part of a lookup.

Unknown schema/codec versions fail with a rebuild/new-path instruction. These are
recomputable observations: retain a copy and choose a new file rather than forcing an
incompatible cache open. Corrupt entries log a warning and miss. No pickle or arbitrary
object stringification is used. API contract fingerprints and TTLs do not guarantee a
frozen provider dataset. Cache writes and durable run advancement are independent.

### Run-store ownership

SQLiteRunStore stores versioned complete QueryExecutionState snapshots separately from
lookup cache and observation archives. Choose an explicit local path; no persistence
is enabled by default. RunDefinition.capture(registry, prepared) retains immutable
settings/plans and declared source identities. Call definition.validate(registry,
worker_identity=...) before continuing a loaded state; changed identities require a
new run. A saved fingerprint does not freeze a remote provider.

create() returns revision 0. claim(run_id, revision=..., lease_seconds=60) grants an
opaque owner token. Every save/renew/finish/release requires the current revision and
owner and returns a new revision. Renew before expiry; an expired token cannot write.
A crashed owner blocks takeover only until its bounded lease expires. release() leaves
the last saved state paused. finish() accepts a done query and releases ownership;
review results retain review status. It does not choose candidates.

Transactions contain only snapshot validation/storage, never source calls or human waits.
A crash during save retains either the previous snapshot or the whole next snapshot.
Unapplied interrupted waves may repeat upstream reads. Cache hits are observations, not
run progress. Use local disk, not cross-host/network SQLite. Run schema version 1 has
no automatic destructive migration: retain the file for migration and use a new path
when incompatible. Runs have no automatic retention/deletion policy; keep backups and
remove an old store only when no owners use it. CLI, Python and browser controls are available as described below.

### Managed continuation and review

CLI commands and review-choice syntax are described above. `--lease-seconds`
defaults to 60 and is renewed during execution. The following complete Python
script creates a managed query; choose a new `run_id` for a new run.

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

For saved reviews, use `continue_run` with explicit `ReviewDecision` values; see
[the public continuation service](../braidworks-core/src/braidworks/core/persistent_query.py).


The managed service renews ownership while running and releases the last saved
checkpoint on cancellation. Resume validates source identities and saved settings;
completed runs return saved results without new source calls. A run left by a crashed
process can be claimed after lease expiry. An in-flight synchronous backend thread
may finish after cancellation, but its unapplied result does not advance the checkpoint.

Browser controls use the same options; paths are local to the server, not the browser.
Recipes and generated commands retain operational paths, so review them before sharing.
Lookup-cache files can be recreated. Run stores contain original inputs, observations
and decisions: back them up if that history matters. Close all owners before removing
a file; there is no automatic retention or deletion. Query-state version 2 reads
version 1, but older review checkpoints without continuation context cannot safely
apply choices: retain their history and start a new run. Unknown storage/schema versions
fail rather than overwrite data. No persistence is enabled without explicit paths.
