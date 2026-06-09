# braidworks-arq

Distributed execution for Braidworks: run weave-steps on [arq](https://arq-docs.helpmanual.io/)
workers over Redis. You get a **durable queue** (steps survive a worker crash and
retry), **cross-machine fan-out** (entities and concurrent braids/branches spread
across workers), and **cluster-wide rate limiting** against shared upstreams (e.g.
NCBI) — without changing any orchestration logic.

arq is **async-native**, which matches braidworks: the orchestrator and weavers are
already `async`, so dispatching a step is `await` all the way down — no thread bridge,
no `asyncio.run` per task, no result-join guard.

## How it fits

It plugs into braidworks-core's `WeaveStepRunner` seam. All orchestration — planning,
caching, backend fallback, classification, review queue, wave/branch concurrency —
stays in core's `LocalExecutor`, in-process. Only the per-step `execute_batch` call is
dispatched to a worker:

```
LocalExecutor (orchestrator)
  └─ ArqStepRunner.run_step(...)               # this package
       └─ await pool.enqueue_job("weave_step", ..., _queue_name="weaver.<id>")
            └─ weave_step coroutine on a worker
                 └─ await weaver.execute_batch(...)
```

A weave-step is a pure, cache-keyed function of `(weaver_id, capability_id, backend,
input StrandSets, requested_outputs)` plus the backend fingerprint, and all of those
serialize to JSON — which is what makes moving it off-process safe and idempotent.

## Usage

```python
from braidworks_arq import build_distributed_executor, build_registry_from_entry_points

registry = build_registry_from_entry_points()       # orchestrator: manifests/planning
executor = build_distributed_executor(registry)      # dispatches steps to workers
result = await executor.execute(braid, strand_sets)  # same API as LocalExecutor
```

Run workers (one queue per weaver, so a worker only needs the data its weaver uses):

```bash
make worker WEAVER=ncbi       # serves the weaver.ncbi queue, loads only the ncbi weaver
make worker WEAVER=disbiome
```

Configuration (all env, all optional):

| Variable | Default | Meaning |
|---|---|---|
| `BRAIDWORKS_REDIS_URL` | `redis://localhost:6379/0` | Redis for the queue + job results |
| `BRAIDWORKS_QUEUE` | `weaver.default` | the queue a worker consumes (set to `weaver.<id>`) |
| `BRAIDWORKS_WEAVERS` | _(all)_ | comma list of weaver ids to load into a worker |
| `BRAIDWORKS_RATE_LIMITS` | _(off)_ | `weaver[:backend]=per_sec`, e.g. `ncbi:api=3` |

### Worker discovery

Workers find weavers through the `braidworks.weavers` entry-point group (name =
`weaver_id`, value = a zero-arg builder). A `pip install`-ed weaver is servable with
no change here. `BRAIDWORKS_WEAVERS` (or `build_registry_from_entry_points(only=...)`)
restricts a worker to the weavers whose data it holds.

## Durability

- arq stores jobs in Redis and re-queues a job whose worker died mid-run (the
  in-progress lock expires), bounded by `max_tries`.
- `weave_step` distinguishes failure kinds: control-flow exceptions
  (`BackendUnavailable` / `BackendConfigurationError`) propagate immediately so the
  orchestrator's backend fallback handles them; any other exception is retried with
  backoff (arq `Retry`) until `MAX_TRIES`, then surfaces as `WeaveStatus.ERROR`.

## Tests

`make test` runs the suite **inline — no Redis required** (an in-process pool double
runs the task coroutine directly). The Redis Lua token bucket is verified against a
real Redis in `tests/test_integration_redis.py`, skipped unless
`BRAIDWORKS_REDIS_TEST=<redis url>` is set.
