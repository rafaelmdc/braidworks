"""Task body, runner, and distributed executor — run inline (no Redis)."""

from __future__ import annotations

import pytest
from arq.worker import Retry

from braidworks.core.braid import BackendPolicy, FallbackCondition
from braidworks.core.exceptions import BackendUnavailable
from braidworks.core.planner import Braider

from braidworks_arq import discovery
from braidworks_arq.executor import build_distributed_executor
from braidworks_arq.runner import ArqStepRunner
from braidworks_arq.tasks import weave_step

from fakes import (
    DIS,
    NAME,
    TAXID,
    TRAIT,
    EchoWeaver,
    FlakyWeaver,
    InlinePool,
    branch_registry,
    name_sets,
    registry_with,
    single_step_braid,
)


def _payload(*names: str):
    return [ss.to_json() for ss in name_sets(*names)]


# --- task body ----------------------------------------------------------------


async def test_weave_step_runs_a_batch():
    weaver = EchoWeaver()
    discovery.set_registry(registry_with(weaver))
    out = await weave_step({"job_try": 1, "redis": None}, "fake", "fake.resolve", "local", _payload("a", "b"), [TAXID])
    assert len(out) == 2 and all(r["status"] == "ok" for r in out)
    assert weaver.batch_calls == 1


async def test_control_exception_propagates_not_retried():
    discovery.set_registry(registry_with(FlakyWeaver(unavailable_backend="local")))
    with pytest.raises(BackendUnavailable):
        await weave_step({"job_try": 1, "redis": None}, "fake", "fake.resolve", "local", _payload("x"), [TAXID])


async def test_transient_error_defers_retry_then_surfaces():
    class Boom(EchoWeaver):
        async def execute_batch(self, *a, **k):
            raise RuntimeError("upstream hiccup")

    discovery.set_registry(registry_with(Boom()))
    # Early attempt → arq Retry (deferred).
    with pytest.raises(Retry):
        await weave_step({"job_try": 1, "redis": None}, "fake", "fake.resolve", "local", _payload("x"), [TAXID])
    # Final attempt → the original error surfaces.
    with pytest.raises(RuntimeError, match="upstream hiccup"):
        await weave_step({"job_try": 3, "redis": None}, "fake", "fake.resolve", "local", _payload("x"), [TAXID])


# --- runner + executor (inline pool) ------------------------------------------


async def test_runner_dispatches_via_pool():
    weaver = EchoWeaver()
    discovery.set_registry(registry_with(weaver))
    runner = ArqStepRunner(pool=InlinePool(weave_step))
    results = await runner.run_step("fake", "fake.resolve", "local", name_sets("x"), frozenset({TAXID}))
    assert results[0].strands[0].type_id == TAXID


async def test_distributed_executor_resolves():
    weaver = EchoWeaver()
    reg = registry_with(weaver)
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg, pool=InlinePool(weave_step))
    res = await ex.execute(single_step_braid(), name_sets("a", "b", "c"))
    assert len(res.resolved) == 3 and all(ss.has(TAXID) for ss in res.resolved)
    assert weaver.batch_calls == 1


async def test_cache_avoids_a_second_dispatch():
    weaver = EchoWeaver()
    reg = registry_with(weaver)
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg, pool=InlinePool(weave_step))
    braid = single_step_braid()
    await ex.execute(braid, name_sets("a", "b"))
    await ex.execute(braid, name_sets("a", "b"))
    assert weaver.batch_calls == 1  # same values → cache hit, no re-dispatch


async def test_backend_unavailable_triggers_orchestrator_fallback():
    weaver = FlakyWeaver(unavailable_backend="local")
    reg = registry_with(weaver)
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg, pool=InlinePool(weave_step))
    braid = single_step_braid(
        primary="local",
        fallback_backends=("api",),
        fallback_on=frozenset({FallbackCondition.BACKEND_UNAVAILABLE}),
    )
    res = await ex.execute(braid, name_sets("a", "b"))
    assert len(res.resolved) == 2 and all(ss.has(TAXID) for ss in res.resolved)


# --- branch parallelism through the arq runner --------------------------------


async def test_distributed_branch_braid_resolves_all_branches():
    reg = branch_registry()
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg, pool=InlinePool(weave_step))
    braid = Braider(reg).plan(
        frozenset({NAME}), frozenset({TRAIT, DIS}), backend_policy=BackendPolicy.LOCAL_ONLY
    )
    assert len(braid.waves()) == 2
    res = await ex.execute(braid, name_sets("ecoli"))
    assert len(res.resolved) == 1
    got = res.resolved[0]
    assert got.has(TRAIT) and got.has(DIS)


async def test_distributed_partial_branch_resolved_with_completion():
    reg = branch_registry(disease_miss=True)
    discovery.set_registry(reg)
    ex = build_distributed_executor(reg, pool=InlinePool(weave_step))
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
