# WIP — Distributed execution (Celery + Redis) implementation plan

> **TEMPORARY working doc.** Delete this file once the broker work has landed and
> `docs/architecture.md` has absorbed whatever is worth keeping. It exists so the
> implementation can be picked up mid-stream without re-deriving the design.

## Goal

Turn braidworks' in-process `LocalExecutor` into something that *can* run as a real
async broker: durable queue, cross-machine fan-out, and global backpressure against
rate-limited upstreams (NCBI). Decided: **Celery + Redis**, **Full Phase 1**, worker
registry via **entry-point discovery**.

## Core insight — one seam

Do **not** distribute the orchestration. All the valuable logic in `LocalExecutor`
(cache split, backend fallback, `_classify`, review queue, merge, chunking) is pure
orchestration over returned `WeaveResult`s and stays exactly where it is. Extract
only the weaver call behind an interface:

```python
class WeaveStepRunner(Protocol):
    async def run_step(
        self,
        weaver_id: str,
        capability_id: str,
        backend: str,
        strand_sets: list[StrandSet],
        requested_outputs: frozenset[str],
    ) -> list[WeaveResult]: ...
```

- `LocalExecutor` gets an injected runner; default = in-process runner that calls
  `weaver.execute_batch` (current behavior, byte-for-byte). Fully backwards-compatible.
- `braidworks-celery` (new workspace package) provides `CeleryStepRunner` +
  the `weave_step` Celery task + a `DistributedExecutor`.
- Backend fallback stays orchestrator-side → the task is dead-simple and idempotent.

Why this works: `StrandSet`/`WeaveResult`/`CapabilityInvocation` already
`to_json`/`from_json`, and `weaver.execute_batch(...)` is already pure + cache-keyed
(`compute_cache_key`). v0.1.1 canonical types mean identical inputs hash identically
across processes.

## Constraints baked into the design

- **Data locality, not statelessness.** Workers need their weaver's local DB present
  (taxdump multi-GB). → **per-weaver queues**: route `weave_step` for `ncbi` to the
  `ncbi` queue; only NCBI-provisioned workers consume it.
- **Async weaver vs sync Celery.** Task body = `asyncio.run(weaver.execute_batch(...))`.
  Orchestrator awaits via `asyncio.to_thread(async_result.get)`. Friction is real →
  keep everything behind `WeaveStepRunner` so we can swap to `arq` later untouched.
- **Intra-braid branch parallelism is Phase 2.** `Braider` emits a *linear* topo list,
  not the DAG. Phase 1 parallelism = entity fan-out + concurrent braids. Branch
  parallelism needs the planner to expose independent steps (Phase 2).
- **Core stays pure.** Core only gains the Protocol + runner injection — no celery/redis
  dependency. Backwards-compatible `0.1.2` core bump.

## Worker registry: entry-point discovery

Each weaver package exposes a `braidworks.weavers` entry point pointing at a
zero-arg `register(registry)` (or a provider). Workers build their `BraidRegistry`
by iterating installed entry points. Matches the existing provider/factory pattern.
Per-weaver queue name derives from `weaver_id`.

---

## Execution plan (stacked branches/PRs off main)

### PR 1 — core seam (`braidworks-core` 0.1.2, backwards-compatible)
Branch: `feat/weave-step-runner-seam`
- [ ] Add `WeaveStepRunner` Protocol + `InProcessStepRunner` (calls `weaver.execute_batch`)
      in core (new module `braidworks/core/runner.py`).
- [ ] `LocalExecutor.__init__` takes optional `runner: WeaveStepRunner | None`;
      default constructs `InProcessStepRunner(registry)`. Replace the direct
      `weaver.execute_batch` call in `_call_batch` with `runner.run_step(...)`.
      Backend fallback / sub-batch chunking stays in the executor.
- [ ] Export new symbols from `braidworks.core.__init__`.
- [ ] Tests: existing suite green unchanged + a test that injecting a custom runner
      is observed (records calls / can stub results).
- [ ] Bump core 0.1.1 → 0.1.2 (minor, additive). Floors stay `>=0.1.1` (no break).
- [ ] PR, merge, tag `braidworks-core-v0.1.2`.

### PR 2 — `braidworks-celery` package (depends on core>=0.1.2)
Branch: `feat/braidworks-celery` (stacked on PR1)
- [ ] New workspace member `braidworks-celery/` (pyproject: core>=0.1.2, celery, redis).
- [ ] `app.py`: Celery app (Redis broker + result backend, `acks_late=True`,
      `task_reject_on_worker_lost=True`, retry w/ exponential backoff, dead-letter).
- [ ] `discovery.py`: build a `BraidRegistry` from `braidworks.weavers` entry points.
- [ ] `tasks.py`: `weave_step(...)` task — rebuild/cached registry, deserialize
      StrandSets, `asyncio.run(weaver.execute_batch(...))`, serialize results.
- [ ] `runner.py`: `CeleryStepRunner` implementing `WeaveStepRunner` — submit to the
      per-weaver queue, `await asyncio.to_thread(result.get, timeout=...)`.
- [ ] `executor.py`: `DistributedExecutor` = `LocalExecutor` wired with `CeleryStepRunner`
      (or just document `LocalExecutor(registry, runner=CeleryStepRunner(...))`).
- [ ] Per-weaver queues + Redis token-bucket rate-limit for API-backed steps (NCBI).
- [ ] Add `register` entry points to the existing weavers (taxon/bacdive/disbiome).
- [ ] Tests: `task_always_eager` unit tests (no Redis) + an opt-in integration test
      gated on a real Redis (docker), covering crash-retry, concurrent braids,
      entity fan-out across workers, rate-limit throttle.
- [ ] PR, merge, tag `braidworks-celery-v0.1.0`.

### PR 3 (Phase 2, later) — true parallel paths
Branch: `feat/braid-dag-parallelism`
- [ ] `Braider` exposes the step dependency DAG (independent steps).
- [ ] `DistributedExecutor` submits independent branches as a Celery `group`/`chord`.

---

## Status log (update as we go)
- 2026-06-09: plan written. Decisions: Full Phase 1, entry-point discovery.
