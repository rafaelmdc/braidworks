"""End-to-end (eager) tests: task, runner, and the distributed executor wiring."""

from __future__ import annotations

import pytest

from braidworks.core.braid import BackendPolicy, FallbackCondition
from braidworks.core.planner import Braider

from braidworks_celery import discovery
from braidworks_celery.executor import build_distributed_executor
from braidworks_celery.runner import CeleryStepRunner
from braidworks_celery.tasks import weave_step

from fakes import (
    DIS,
    TRAIT,
    EchoWeaver,
    FlakyWeaver,
    branch_registry,
    name_sets,
    registry_with,
    single_step_braid,
)

NAME = "organism.name"
TAXID = "ncbi.taxon.id"


def test_weave_step_task_runs_a_batch():
    weaver = EchoWeaver()
    discovery.set_registry(registry_with(weaver))
    payload = [ss.to_json() for ss in name_sets("a", "b")]
    out = weave_step.apply_async(
        args=["fake", "fake.resolve", "local", payload, [TAXID]]
    ).get()
    assert len(out) == 2
    assert all(r["status"] == "ok" for r in out)
    assert weaver.batch_calls == 1


async def test_celery_runner_returns_weave_results():
    weaver = EchoWeaver()
    discovery.set_registry(registry_with(weaver))
    runner = CeleryStepRunner()
    results = await runner.run_step("fake", "fake.resolve", "local", name_sets("x"), frozenset({TAXID}))
    assert len(results) == 1
    assert results[0].strands[0].type_id == TAXID


async def test_distributed_executor_resolves_via_the_task():
    weaver = EchoWeaver()
    reg = registry_with(weaver)
    discovery.set_registry(reg)  # the "worker" side resolves the weaver here
    ex = build_distributed_executor(reg)  # the orchestrator side
    res = await ex.execute(single_step_braid(), name_sets("a", "b", "c"))
    assert len(res.resolved) == 3
    assert all(ss.has(TAXID) for ss in res.resolved)
    assert weaver.batch_calls == 1


async def test_executor_cache_avoids_a_second_dispatch():
    weaver = EchoWeaver()
    reg = registry_with(weaver)
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg)
    braid = single_step_braid()
    await ex.execute(braid, name_sets("a", "b"))
    assert weaver.batch_calls == 1
    await ex.execute(braid, name_sets("a", "b"))  # same values → cache hit, no dispatch
    assert weaver.batch_calls == 1


async def test_backend_unavailable_in_worker_triggers_orchestrator_fallback():
    """A BackendUnavailable raised *in the worker* must propagate so fallback works.

    The weaver's ``local`` backend is down; the braid falls back to ``api``. The
    distributed runner surfaces the control exception untouched (no retry), and the
    executor retries the step on the next backend — resolving the entity.
    """
    weaver = FlakyWeaver(unavailable_backend="local")
    reg = registry_with(weaver)
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg)
    braid = single_step_braid(
        primary="local",
        fallback_backends=("api",),
        fallback_on=frozenset({FallbackCondition.BACKEND_UNAVAILABLE}),
    )
    res = await ex.execute(braid, name_sets("a", "b"))
    assert len(res.resolved) == 2
    assert all(ss.has(TAXID) for ss in res.resolved)


async def test_distributed_branch_braid_dispatches_each_branch_step():
    """A branched braid resolves through the Celery runner; each branch is its own step."""
    reg = branch_registry()
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg)
    braid = Braider(reg).plan(
        frozenset({NAME}), frozenset({TRAIT, DIS}), backend_policy=BackendPolicy.LOCAL_ONLY
    )
    assert len(braid.waves()) == 2  # ncbi, then the two independent branches
    res = await ex.execute(braid, name_sets("ecoli"))
    assert len(res.resolved) == 1
    got = res.resolved[0]
    assert got.has(TRAIT) and got.has(DIS)


async def test_distributed_partial_branch_is_resolved_with_completion():
    reg = branch_registry(disease_miss=True)
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg)
    braid = Braider(reg).plan(
        frozenset({NAME}), frozenset({TRAIT, DIS}), backend_policy=BackendPolicy.LOCAL_ONLY
    )
    res = await ex.execute(braid, name_sets("ecoli"))
    assert len(res.resolved) == 1 and res.unresolved == []
    ss = res.resolved[0]
    assert ss.has(TRAIT) and not ss.has(DIS)
    outcomes = {o.capability_id: o.status for o in ss.completion}
    assert outcomes["bacdive.traits"] == "ok"
    assert outcomes["disbiome.assoc"] == "no_match"


async def test_transient_error_is_retried_then_surfaces():
    """A non-control exception is retried (backoff) and ultimately surfaces.

    In Celery eager mode ``self.retry`` raises ``Retry`` rather than looping, so we
    assert the runner surfaces a failure (real retry-exhaustion is exercised against
    a live worker; see the README)."""

    class Boom(EchoWeaver):
        async def execute_batch(self, *a, **k):
            raise RuntimeError("upstream hiccup")

    discovery.set_registry(registry_with(Boom()))
    runner = CeleryStepRunner()
    with pytest.raises(Exception):  # noqa: B017 - Retry (eager) or RuntimeError (worker)
        await runner.run_step("fake", "fake.resolve", "local", name_sets("x"), frozenset({TAXID}))
