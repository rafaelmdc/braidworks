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
    out = await weave_step(
        {"job_try": 1, "redis": None}, "fake", "fake.resolve", "local", _payload("a", "b"), [TAXID]
    )
    assert len(out) == 2 and all(r["status"] == "ok" for r in out)
    assert weaver.batch_calls == 1


async def test_control_exception_propagates_not_retried():
    discovery.set_registry(registry_with(FlakyWeaver(unavailable_backend="local")))
    with pytest.raises(BackendUnavailable):
        await weave_step(
            {"job_try": 1, "redis": None}, "fake", "fake.resolve", "local", _payload("x"), [TAXID]
        )


async def test_transient_error_defers_retry_then_surfaces():
    class Boom(EchoWeaver):
        async def execute_batch(self, *a, **k):
            raise TimeoutError("upstream hiccup")

    discovery.set_registry(registry_with(Boom()))
    # Early attempt → arq Retry (deferred).
    with pytest.raises(Retry):
        await weave_step(
            {"job_try": 1, "redis": None}, "fake", "fake.resolve", "local", _payload("x"), [TAXID]
        )
    # Final attempt → the original error surfaces.
    with pytest.raises(TimeoutError, match="upstream hiccup"):
        await weave_step(
            {"job_try": 3, "redis": None}, "fake", "fake.resolve", "local", _payload("x"), [TAXID]
        )


# --- runner + executor (inline pool) ------------------------------------------


async def test_runner_dispatches_via_pool():
    weaver = EchoWeaver()
    discovery.set_registry(registry_with(weaver))
    runner = ArqStepRunner(pool=InlinePool(weave_step))
    results = await runner.run_step(
        "fake", "fake.resolve", "local", name_sets("x"), frozenset({TAXID})
    )
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
    ex = build_distributed_executor(
        reg, pool=InlinePool(weave_step), assume_homogeneous_workers=True
    )
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


async def test_default_distributed_execution_does_not_reuse_unverified_cache():
    weaver = EchoWeaver()
    reg = registry_with(weaver)
    discovery.set_registry(reg)
    executor = build_distributed_executor(reg, pool=InlinePool(weave_step))
    for _ in range(2):
        await executor.execute(single_step_braid(), name_sets("a"))
    assert weaver.batch_calls == 2


async def test_mismatched_worker_dataset_aborts_before_fetch():
    from braidworks.core.exceptions import BackendConfigurationError

    reg = registry_with(EchoWeaver(dataset="expected"))
    worker = EchoWeaver(dataset="different")
    discovery.set_registry(registry_with(worker))
    executor = build_distributed_executor(reg, pool=InlinePool(weave_step))
    with pytest.raises(BackendConfigurationError, match="worker identity mismatch"):
        await executor.execute(single_step_braid(), name_sets("a"))
    assert worker.batch_calls == 0


def test_distributed_cache_requires_explicit_fleet_assertion():
    from braidworks.core.cache import InMemoryStrandCache

    with pytest.raises(ValueError, match="homogeneous"):
        build_distributed_executor(registry_with(EchoWeaver()), cache=InMemoryStrandCache())


async def test_worker_charges_http_roundtrips_instead_of_batch_size(monkeypatch):
    import httpx
    from braidworks.core.http_pacing import PacedHTTPClient
    from braidworks_arq import tasks

    payments = []

    class Bucket:
        def __init__(self, *args, **kwargs):
            assert kwargs["capacity"] == 1

        async def acquire(self):
            payments.append(1)
            return True

    monkeypatch.setattr(tasks, "TokenBucket", Bucket)
    monkeypatch.setenv("BRAIDWORKS_RATE_LIMITS", "fake:local=2")

    def respond(request):
        return (
            httpx.Response(302, headers={"location": "/page1"})
            if request.url.path == "/start"
            else httpx.Response(200)
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
        base_url="https://fixture.test",
        follow_redirects=True,
    ) as client:

        class HTTPWeaver(EchoWeaver):
            def supports_request_pacing(self, backend):
                return True

            async def execute_batch(self, *args, **kwargs):
                http = PacedHTTPClient(client, "fake", "local")
                await http.get("/start")
                await http.get("/page2")
                return await super().execute_batch(*args, **kwargs)

        discovery.set_registry(registry_with(HTTPWeaver()))
        results = await weave_step(
            {"redis": None},
            "fake",
            "fake.resolve",
            "local",
            _payload(*[f"q{i}" for i in range(10)]),
            [TAXID],
        )
        assert len(results) == 10
        assert len(payments) == 3  # redirect + page1 + page2, not ten inputs


async def test_worker_refuses_budget_for_uninstrumented_backend(monkeypatch):
    from braidworks.core.exceptions import BackendConfigurationError

    monkeypatch.setenv("BRAIDWORKS_RATE_LIMITS", "fake:local=2")
    weaver = EchoWeaver()
    discovery.set_registry(registry_with(weaver))
    with pytest.raises(BackendConfigurationError, match="does not declare request pacing"):
        await weave_step({"redis": None}, "fake", "fake.resolve", "local", _payload("q"), [TAXID])
    assert weaver.batch_calls == 0
