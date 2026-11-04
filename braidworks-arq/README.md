# braidworks-arq

Distributed execution for Braidworks: run weave-steps on [arq](https://arq-docs.helpmanual.io/)
workers over Redis. You get a **durable queue** (steps survive a worker crash and
retry), **cross-machine fan-out** (entities and concurrent braids/branches spread
across workers), and **cluster-wide HTTP request pacing** against shared upstreams (e.g.
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

A weave-step is identified for caching by `(weaver_id, capability_id, backend,
input StrandSets, requested_outputs, effective parameters)` plus the backend fingerprint.
The executor sends the expected manifest and backend fingerprint to each dispatched
worker; a mismatch aborts before fetching rather than mixing datasets or package versions.
Deploy matching orchestrator and worker versions together when upgrading this protocol.

Distributed caching is disabled by default: an orchestrator fingerprint cannot establish
the identity of every worker, and a cache hit would bypass the worker check. Set
`assume_homogeneous_workers=True` only when deployment controls guarantee identical
manifests and backend fingerprints across the fleet for the executor lifetime. A custom
`cache=` requires that explicit assertion. Checks on dispatched jobs still apply.
This does not validate an entire fleet or freeze a mutable upstream API.

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
| `BRAIDWORKS_RATE_LIMITS` | _(no explicit rules)_ | `weaver[:backend]=requests_per_sec`, e.g. `ncbi:api=3` |
| `BRAIDWORKS_FANOUT` | _(off)_ | `weaver[:backend]=width` — split a step's batch across up to `width` concurrent workers |
| `BRAIDWORKS_FANOUT_UNBUDGETED` | _(empty)_ | `weaver[:backend]` list asserted to make **no** rate-limited external calls (local-DB backends) |
| `BRAIDWORKS_FANOUT_CHUNK` | _(auto)_ | `weaver[:backend]=N` entities-per-task override |

Workers install a request-budget callback for every job. Without a matching explicit
rate rule, that callback charges no pacing budget; source-local defaults do not
supply a Redis limit. Configure `BRAIDWORKS_RATE_LIMITS` entries for cluster-wide
pacing. Local source defaults described in [request pacing](../docs/request-pacing.md)
apply when no executor budget overrides them.

### Entity-level fan-out

By default a step's whole batch runs as one job on one worker. For bulk workloads,
fan-out splits the batch into contiguous chunks dispatched as **concurrent jobs**, so
multiple workers process one batch in parallel; results are gathered back in input
order. It is opt-in per `weaver:backend` and requires a dispatch budget or an
explicit assertion that the backend makes no rate-limited external calls.

- Local backends can use `BRAIDWORKS_FANOUT=ncbi:local=8` with
  `BRAIDWORKS_FANOUT_UNBUDGETED=ncbi:local`.
- External backends require a `BRAIDWORKS_RATE_LIMITS` entry. Missing both a budget
  and an unbudgeted assertion raises `FanoutConfigError`. Workers charge one token
  immediately before each HTTP request, including redirects, pagination and polling.
  Bulk requests cost one token regardless of their number of input identifiers.
  Budgeted and local backends split evenly across the configured width.

Redis server time controls refill. Buckets have capacity one, preventing an initial
burst, and workers must agree on rates and capacity for a shared bucket. Conflicting
configurations fail explicitly. A cancelled wait sends no request; already sent
requests retain their charges. Third-party backends must declare request pacing support
and use core's `PacedHTTPClient` for every HTTP call; configured unsupported backends
fail before execution. See [request pacing](../docs/request-pacing.md).

### Worker discovery

Workers find weavers through the `braidworks.weavers` entry-point group (name =
`weaver_id`, value = a zero-arg builder). A `pip install`-ed weaver is servable with
no change here. `BRAIDWORKS_WEAVERS` (or `build_registry_from_entry_points(only=...)`)
restricts a worker to the weavers whose data it holds.

## Durability

- arq stores jobs in Redis and re-queues a job whose worker died mid-run (the
  in-progress lock expires), bounded by `max_tries`.
- `weave_step` retries only known connection/timeout exceptions, with the existing
  jittered exponential delay and **three total attempts**. On the last attempt the
  original exception propagates. Each attempt executes the batch once.
- `BackendUnavailable` propagates for executor fallback; configuration/unsupported
  requests, contract violations, programming errors and unknown exceptions fail
  immediately. `BackendConfigurationError` aborts the run rather than invoking fallback.
- `NO_MATCH` / `ERROR` results are returned unchanged for executor policy. Worker retry
  does not infer transience from result messages or source HTTP status codes.

| Exception/result | Worker decision |
|---|---|
| Python `ConnectionError` / `TimeoutError` | Retry within the attempt limit |
| Redis connection/timeout errors | Retry, excluding authentication/authorization errors |
| HTTPX `NetworkError` / `TimeoutException`, when HTTPX is installed | Retry within the attempt limit |
| Domain errors, Redis auth errors, programming/unknown exceptions, other local I/O errors | Propagate immediately |
| HTTP status exception (including 429/5xx) | Propagate; status policy belongs in the source backend |
| Returned `NO_MATCH` / `ERROR` | Return unchanged; executor owns fallback |
| Cancellation | Propagate immediately |

The pure `braidworks_arq.retry.should_retry` function makes this decision. It uses
concrete exception types rather than message matching. HTTPX stays optional for workers
serving non-HTTP sources; no core HTTP dependency or exception hierarchy changed.
Retry covers exceptions raised during batch execution (including request-budget charges);
identity, input and worker setup checks retain their immediate failure behavior.

## Tests

`make test` runs the suite **inline — no Redis required** (an in-process pool double
runs the task coroutine directly). The Redis Lua token bucket is verified against a
real Redis in `tests/test_integration_redis.py`, skipped unless
`BRAIDWORKS_REDIS_TEST=<redis url>` is set.

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/braidworks-arq/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.
