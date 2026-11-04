# Cache and run-store contracts

Storage policies, ownership and compatibility for applications and operators.
For creating or continuing a query, see [the saved-run guide](../persistence.md).

## Lookup cache

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
shrinking the file. Physical reclamation requires administrative SQLite
checkpoint/VACUUM operations when no executions use the file; lookups do not shrink it.

Unknown schema/codec versions fail with a rebuild/new-path instruction. These are
recomputable observations: retain a copy and choose a new file rather than forcing an
incompatible cache open. Corrupt entries log a warning and miss. No pickle or arbitrary
object stringification is used. API contract fingerprints and TTLs do not guarantee a
frozen provider dataset. Cache writes and durable run advancement are independent.

## Run-store ownership

SQLiteRunStore stores versioned complete QueryExecutionState snapshots separately from
lookup cache and observation archives. Choose an explicit local path; no persistence
is enabled by default. RunDefinition.capture(registry, prepared) retains immutable
settings/plans and declared source identities. Call definition.validate(registry,
worker_identity=...) before continuing a loaded state; changed identities require a
new run. A saved fingerprint does not freeze a remote provider.

| Operation | Contract |
|---|---|
| `create()` | Returns revision 0. |
| `claim(run_id, revision=..., lease_seconds=60)` | Grants an opaque owner token with a bounded lease. |
| `save`, `renew`, `finish`, `release` | Require the current revision and owner; return a new revision. An expired owner cannot write. |
| `release()` | Leaves the last saved state paused. |
| `finish()` | Accepts a done query and releases ownership; review results retain review status. It does not choose candidates. |

A crashed owner blocks takeover only until its lease expires. The managed service
renews while executing; CLI `--lease-seconds` defaults to 60.

Transactions contain only snapshot validation/storage, never source calls or human waits.
A crash during save retains either the previous snapshot or the whole next snapshot.
Unapplied interrupted waves may repeat upstream reads. Cache hits are observations, not
run progress. Use local disk, not cross-host/network SQLite. Run schema version 1 has
no automatic destructive migration: retain the file for migration and use a new path
when incompatible. Runs have no automatic retention/deletion policy; keep backups and
remove an old store only when no owners use it. CLI, Python and browser tasks are
described in the [saved-run guide](../persistence.md).

## Managed continuation and compatibility

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

Public interfaces: [run stores](../../braidworks-core/src/braidworks/core/run_store.py),
[managed continuation](../../braidworks-core/src/braidworks/core/persistent_query.py),
and [persistence options](../../braidworks-core/src/braidworks/core/persistence_options.py).
