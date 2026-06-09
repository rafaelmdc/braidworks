# braidworks-celery

Distributed execution for Braidworks: run weave-steps on [Celery](https://docs.celeryq.dev/)
workers over a Redis broker. You get a **durable queue** (steps survive a worker
crash and retry), **cross-machine fan-out** (entities and concurrent braids spread
across workers), and **cluster-wide rate limiting** against shared upstreams (e.g.
NCBI) — without changing any orchestration logic.

## How it fits

It plugs into braidworks-core's `WeaveStepRunner` seam. All orchestration —
planning, caching, backend fallback, classification, the review queue, merging —
stays in core's `LocalExecutor`, in-process. Only the per-step `execute_batch` call
is dispatched to a worker:

```
LocalExecutor (orchestrator)
  └─ CeleryStepRunner.run_step(...)        # this package
       └─ weave_step task on queue "weaver.<id>"   # runs on a worker
            └─ weaver.execute_batch(...)   # the actual data source
```

A weave-step is a pure, cache-keyed function of `(weaver_id, capability_id, backend,
input StrandSets, requested_outputs)` plus the backend fingerprint, and every one of
those serializes to JSON — which is what makes moving it off-process safe and
idempotent.

## Usage

```python
from braidworks_celery import build_distributed_executor, build_registry_from_entry_points

registry = build_registry_from_entry_points()       # orchestrator: manifests/planning
executor = build_distributed_executor(registry)      # dispatches steps to workers
result = await executor.execute(braid, strand_sets)  # same API as LocalExecutor
```

Run workers (one queue per weaver, so a worker only needs the data its weaver uses):

```bash
make worker WEAVER=ncbi       # serves the weaver.ncbi queue
make worker WEAVER=disbiome   # serves the weaver.disbiome queue
```

Configuration (all env, all optional):

| Variable | Default | Meaning |
|---|---|---|
| `BRAIDWORKS_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `BRAIDWORKS_RESULT_BACKEND` | `redis://localhost:6379/0` | result backend |
| `BRAIDWORKS_RATE_LIMITS` | _(off)_ | `weaver[:backend]=per_sec`, comma-separated, e.g. `ncbi:api=3` |

### Worker discovery

Workers find weavers through the `braidworks.weavers` entry-point group (name =
`weaver_id`, value = a zero-arg builder). A `pip install`-ed weaver is servable with
no change here. Restrict a worker to the weavers whose data it holds with
`build_registry_from_entry_points(only={"ncbi"})` + `set_registry(...)`.

## Durability

- `task_acks_late` + `task_reject_on_worker_lost`: a step is acked only after it
  finishes, so a crash mid-step re-queues it rather than losing it.
- `autoretry_for=(Exception,)` with exponential backoff + jitter (`max_retries=3`):
  transient upstream failures retry; a persistent failure surfaces to the executor
  as a `WeaveStatus.ERROR`, handled by its normal `ErrorPolicy`.

## Tests

`make test` runs the suite in Celery **eager** mode — no broker required. The Lua
token bucket is verified against a real Redis in `tests/test_integration_redis.py`,
which is skipped unless `BRAIDWORKS_REDIS_TEST=<redis url>` is set.
