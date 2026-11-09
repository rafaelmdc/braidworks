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
see [choose and set up sources](choose-sources.md) for acquisition and [NCBI setup](set-up-ncbi-database.md) for taxonomy.

## Start and inspect a saved query

From the checkout, with UniProt and PDBe installed:

```bash
uv run braidworks get P04637 --have protein.query \
    --want protein.name,structure.pdb.ids \
    --cache-db data/lookups.sqlite --run-db data/runs.sqlite --run-id p53-structures
uv run braidworks runs --run-db data/runs.sqlite
uv run braidworks runs p53-structures --run-db data/runs.sqlite --format json
uv run braidworks resume p53-structures --run-db data/runs.sqlite --format json
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
uv run braidworks resume RUN_ID --run-db data/runs.sqlite \
    --decision node:0=select:0
```

Candidate indices are zero-based. `KEY=accept` approves a successful observation
that needs review; `KEY=reject` leaves that row unresolved. Repeat `--decision` for
independent items. A decision applies only to that observation; later ambiguous
matches still need review. `--strict` also applies when resuming.

## Save and resume runs from Python

Give a `Session` a run store; every query it runs is then a saved run. Name the run
with `run_id` (a new name: existing runs are never overwritten):

```python
import braidworks as bw

with bw.Session(cache="data/lookups.sqlite", runs="data/runs.sqlite") as s:
    result = s.get(["Bacillus", "Escherichia coli"], have="organism.name",
                   want="ncbi.taxon.id", run_id="genera")
    print(result.run_id, result.summary())
    print(s.runs())   # every saved run: id, status, inputs, rows awaiting review
```

Paused rows stay in the store. Later, in the same or another session, reopen the run,
record decisions and continue; the decisions are saved with the run:

```python
with bw.Session(runs="data/runs.sqlite") as s:
    result = s.resume("genera")
    result.review[0]              # read the candidates first
    result.review[0].choose(0)    # 1386, the bacteria; or .accept() / .reject()
    result = result.resume()
```

`Session.resume` on a finished run returns its saved result without calling any
source. The same store works with `braidworks runs` and `braidworks resume`, so you can
start a run in Python and finish it on the command line, or the reverse.

Browser controls use the same storage options, with paths on the server's disk inside
its data directory (`braidworks serve --data-dir`). Recipes and generated commands
retain those paths; review them before sharing.

## Storage and API reference

[Cache and run-store contracts](../reference/persistence.md) describe TTLs, budgets,
leases, revisions, schemas and retention. Persistence remains opt-in. Keep files on
local disk and back up run history you need to retain. Close owners before removing
files; there is no automatic retention policy.
