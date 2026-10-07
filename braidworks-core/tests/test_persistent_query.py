"""Durable service continuation, cancellation, identity and renewal contracts."""

import asyncio

import pytest
from braidworks.core import QueryOptions, QueryRequest, execute_query, prepare_query
from braidworks.core.persistent_query import continue_run, start_run
from braidworks.core.run_store import RunConflict, SQLiteRunStore
from test_query import _input, _registry


async def test_persistent_result_matches_memory_and_completed_resume_does_no_calls(tmp_path):
    registry = _registry()
    prepared = prepare_query(
        registry, QueryRequest((_input("a", 1), _input("a", 1)), frozenset({"output.value"}))
    )
    expected = await execute_query(registry, prepared)
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    saved = []
    checkpoint = await start_run(
        registry, prepared, store, on_saved=lambda cp: saved.append(cp.to_json())
    )
    assert checkpoint.status == "complete"
    assert checkpoint.state.result.to_json() == expected.to_json()
    assert len(saved) > 2
    calls = registry.get_weaver("a").batch_calls
    resumed = await continue_run(registry, SQLiteRunStore(store.path), checkpoint.run_id)
    assert resumed.to_json() == checkpoint.to_json()
    assert registry.get_weaver("a").batch_calls == calls


async def test_cancel_keeps_complete_checkpoint_and_resume_finishes(tmp_path):
    registry = _registry()
    weaver = registry.get_weaver("a")
    original = weaver.execute_batch
    entered = asyncio.Event()
    released = asyncio.Event()

    async def blocked(*args, **kwargs):
        entered.set()
        await released.wait()
        return await original(*args, **kwargs)

    weaver.execute_batch = blocked
    prepared = prepare_query(registry, QueryRequest((_input("a", 1),), frozenset({"output.value"})))
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    task = asyncio.create_task(start_run(registry, prepared, store, run_id="cancel-me"))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    checkpoint = store.load("cancel-me")
    assert checkpoint.status == "paused" and checkpoint.owner is None
    assert checkpoint.state.active is not None
    assert not checkpoint.state.active.in_wave
    released.set()
    assert (await continue_run(registry, store, "cancel-me")).status == "complete"


async def test_long_query_renews_lease(tmp_path):
    registry = _registry()
    weaver = registry.get_weaver("a")
    original = weaver.execute_batch
    entered = asyncio.Event()
    released = asyncio.Event()

    async def blocked(*args, **kwargs):
        entered.set()
        await released.wait()
        return await original(*args, **kwargs)

    weaver.execute_batch = blocked
    prepared = prepare_query(registry, QueryRequest((_input("a", 1),), frozenset({"output.value"})))

    class TrackingStore(SQLiteRunStore):
        renewed = asyncio.Event()

        def renew(self, *args, **kwargs):
            checkpoint = super().renew(*args, **kwargs)
            self.renewed.set()
            return checkpoint

    store = TrackingStore(tmp_path / "runs.sqlite")
    task = asyncio.create_task(
        start_run(registry, prepared, store, run_id="slow", lease_seconds=0.3)
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await asyncio.wait_for(store.renewed.wait(), 5)
        claimed = store.load("slow")
        assert claimed.owner and claimed.status == "running"
        with pytest.raises(RunConflict, match="live owner"):
            store.claim("slow", revision=claimed.revision)
        released.set()
        assert (await task).status == "complete"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_resume_rejects_source_worker_or_options_before_execution(tmp_path):
    registry = _registry()
    prepared = prepare_query(registry, QueryRequest((_input("a", 1),), frozenset({"output.value"})))
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    completed = await start_run(registry, prepared, store, worker_identity={"worker": "one"})
    with pytest.raises(RunConflict, match="worker"):
        await continue_run(registry, store, completed.run_id, worker_identity={"worker": "two"})
    changed = prepare_query(
        registry,
        QueryRequest(
            (_input("a", 1),), frozenset({"output.value"}), options=QueryOptions(max_expansion=1)
        ),
    )
    with pytest.raises(RunConflict, match="query/options"):
        await continue_run(
            registry,
            store,
            completed.run_id,
            expected_prepared=changed,
            worker_identity={"worker": "one"},
        )
    registry.get_weaver("a").backend_fingerprint = lambda backend: "new-generation"
    with pytest.raises(RunConflict, match="source"):
        await continue_run(registry, store, completed.run_id, worker_identity={"worker": "one"})


async def test_observer_failure_releases_last_saved_state(tmp_path):
    registry = _registry()
    prepared = prepare_query(registry, QueryRequest((_input("a", 1),), frozenset({"output.value"})))
    store = SQLiteRunStore(tmp_path / "runs.sqlite")

    def fail(cp):
        if cp.owner:
            raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer"):
        await start_run(registry, prepared, store, run_id="observed", on_saved=fail)
    assert store.load("observed").status == "paused"
    assert (await continue_run(registry, store, "observed")).status == "complete"


async def test_failed_renewal_cancels_execution_and_preserves_snapshot(tmp_path):
    registry = _registry()
    weaver = registry.get_weaver("a")
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def blocked(*args, **kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    weaver.execute_batch = blocked
    prepared = prepare_query(registry, QueryRequest((_input("a", 1),), frozenset({"output.value"})))

    class FailedRenewalStore(SQLiteRunStore):
        def renew(self, *args, **kwargs):
            raise RunConflict("injected lost lease")

    store = FailedRenewalStore(tmp_path / "runs.sqlite")
    with pytest.raises(RunConflict, match="lost lease"):
        await start_run(registry, prepared, store, run_id="lease-failure", lease_seconds=0.1)
    assert entered.is_set() and cancelled.is_set()
    checkpoint = store.load("lease-failure")
    assert checkpoint.status == "paused" and not checkpoint.state.active.in_wave


async def test_saved_review_never_selects_candidates_implicitly(tmp_path):
    from braidworks.core import (
        BraidRegistry,
        CandidateResult,
        Strand,
        StrandSet,
        WeaveResult,
        WeaveStatus,
    )
    from helpers import ScriptedWeaver, simple_capability

    cap = simple_capability("source.resolve", {"input.id"}, {"output.id"})
    registry = BraidRegistry()

    def ambiguous(ss, backend, outputs):
        return WeaveResult(
            cap.id,
            "1.0.0",
            backend,
            frozenset({"g"}),
            WeaveStatus.AMBIGUOUS,
            candidates=(
                CandidateResult((Strand("output.id", "one"),), 0.9),
                CandidateResult((Strand("output.id", "two"),), 0.8),
            ),
        )

    registry.register(ScriptedWeaver(ambiguous, capability=cap, weaver_id="source"))
    prepared = prepare_query(
        registry,
        QueryRequest(
            (StrandSet.from_strands("duplicate", [Strand("input.id", "x")]),),
            frozenset({"output.id"}),
        ),
    )
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    checkpoint = await start_run(registry, prepared, store)
    assert checkpoint.status == "review" and checkpoint.state.result.review_queue
    resumed = await continue_run(registry, store, checkpoint.run_id)
    assert resumed.to_json() == checkpoint.to_json()
    assert not resumed.state.result.resolved
