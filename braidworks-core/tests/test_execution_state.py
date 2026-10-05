"""Interrupt/reconstruct at every committed boundary, with a fresh runner/cache."""

import json

import pytest
from braidworks.core.execution_state import ExecutionState
from braidworks.core.executor import ExpandPolicy, LocalExecutor, ReviewPolicy
from braidworks.core.planner import Braider
from test_error_tolerance import _input, _reroute_registry
from test_traverse import _inputs
from test_traverse import _registry as fan_registry


@pytest.mark.parametrize("fan", [False, True])
async def test_every_wave_chunk_and_reroute_snapshot_matches_uninterrupted(fan):
    registry = fan_registry() if fan else _reroute_registry()
    if fan:
        braid = Braider(registry).plan_capability("ncbi", "ncbi.list_orthologs")
        inputs = _inputs("7157") + _inputs("7157")
    else:
        braid = Braider(registry).plan(frozenset({"a"}), frozenset({"c"}))
        inputs = _input() + _input()
    for i, ss in enumerate(inputs, 1):
        ss.source_row = i
    snapshots = []
    expected = await LocalExecutor(registry).execute(
        braid,
        inputs,
        expand_policy=ExpandPolicy.all(),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
        chunk_size=1,
        max_expansion=4,
        on_checkpoint=lambda state: snapshots.append(json.loads(json.dumps(state.to_json()))),
    )
    assert snapshots
    for snapshot in snapshots:
        state = ExecutionState.from_json(snapshot)
        assert state.to_json() == snapshot
        actual = await LocalExecutor(registry).continue_state(state)
        assert actual.to_json() == expected.to_json()
        assert actual.total() == expected.total()


async def test_completed_waves_do_not_call_source_again():
    registry = fan_registry()
    braid = Braider(registry).plan_capability("ncbi", "ncbi.list_orthologs")
    snapshots = []
    await LocalExecutor(registry).execute(
        braid,
        _inputs("7157"),
        expand_policy=ExpandPolicy.all(),
        on_checkpoint=lambda state: snapshots.append(state.to_json()),
    )
    state = ExecutionState.from_json(next(s for s in snapshots if s["wave_index"] == 1))
    weaver = registry.get_weaver("ncbi")
    before = weaver.batch_calls
    await LocalExecutor(registry).continue_state(state)
    assert weaver.batch_calls == before


def test_future_snapshot_version_rejected():
    with pytest.raises(ValueError, match="version"):
        ExecutionState.from_json({"version": 999})


async def test_cancelled_unapplied_wave_cannot_be_snapshotted():
    import asyncio

    registry = fan_registry()
    braid = Braider(registry).plan_capability("ncbi", "ncbi.list_orthologs")
    entered = asyncio.Event()

    class Runner:
        async def run_step(self, *args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

    executor = LocalExecutor(registry, runner=Runner())
    state = executor.start_state(braid, _inputs("7157"))
    snapshots = []
    task = asyncio.create_task(
        executor.continue_state(
            state, on_checkpoint=lambda state: snapshots.append(state.to_json())
        )
    )
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ValueError, match="unapplied wave"):
        state.to_json()
    restored = ExecutionState.from_json(snapshots[-1])
    actual = await LocalExecutor(registry).continue_state(restored)
    assert actual.resolved


async def test_selected_candidate_fanout_restores_every_boundary():
    from helpers import ambiguous_result, name_strand_sets, single_step_braid
    from test_fanout import _cand, _setup

    registry, _, executor = _setup(
        lambda ss, backend, requested: ambiguous_result(requested, _cand(1, 0.9), _cand(2, 0.8))
    )
    snapshots = []
    expected = await executor.execute(
        single_step_braid({"ncbi.taxon.id"}),
        name_strand_sets("duplicate", "duplicate"),
        expand_policy=ExpandPolicy.all(),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
        on_checkpoint=lambda state: snapshots.append(state.to_json()),
    )
    for snapshot in snapshots:
        actual = await LocalExecutor(registry).continue_state(ExecutionState.from_json(snapshot))
        assert actual.to_json() == expected.to_json()
        assert actual.total() == 4
