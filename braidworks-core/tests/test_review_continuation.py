"""Explicit decisions retain lineage, phase cursors and future review policy."""

import json

import pytest
from braidworks.core import (
    BraidRegistry,
    CandidateResult,
    QueryOptions,
    QueryRequest,
    Strand,
    StrandSet,
    WeaveResult,
    WeaveStatus,
    prepare_query,
)
from braidworks.core.executor import ExpandPolicy
from braidworks.core.persistent_query import continue_run, start_run
from braidworks.core.query_state import QueryExecutionState
from braidworks.core.review import ReviewDecision, apply_review_decisions
from braidworks.core.run_store import SQLiteRunStore
from helpers import ScriptedWeaver, simple_capability
from test_traverse import GENE, ORTHOLOGS, SYMBOL, _ortholog_result, _orthologs_cap


def _input(value="x", row=1):
    ss = StrandSet.from_strands("same", [Strand("input.id", value)])
    ss.source_row = row
    return ss


def _registry(*, review_second=False):
    registry = BraidRegistry()
    first = simple_capability("first.resolve", {"input.id"}, {"middle.id"})
    second = simple_capability("second.describe", {"middle.id"}, {"output.id"})
    registry.register(
        ScriptedWeaver(
            lambda ss, b, out: WeaveResult(
                first.id,
                "1.0.0",
                b,
                frozenset({"g"}),
                WeaveStatus.AMBIGUOUS,
                candidates=(
                    CandidateResult((Strand("middle.id", "chosen", confidence=0.4),), 0.4),
                    CandidateResult((Strand("middle.id", "other"),), 0.9),
                ),
            ),
            capability=first,
            weaver_id="first",
        )
    )
    registry.register(
        ScriptedWeaver(
            lambda ss, b, out: WeaveResult(
                second.id,
                "1.0.0",
                b,
                frozenset({"g"}),
                WeaveStatus.OK,
                strands=(Strand("output.id", ss.get("middle.id").value),),
                requires_review=review_second,
            ),
            capability=second,
            weaver_id="second",
        )
    )
    return registry


async def test_choose_lower_confidence_preserves_observation_and_remaining_policy(tmp_path):
    registry = _registry(review_second=True)
    prepared = prepare_query(
        registry,
        QueryRequest(
            (_input(),), frozenset({"output.id"}), options=QueryOptions(confidence_threshold=0.8)
        ),
    )
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    paused = await start_run(registry, prepared, store)
    key = paused.state.result.review_queue[0].strand_set.execution_key
    decision = ReviewDecision(key, "select", 0)
    assert ReviewDecision.from_json(decision.to_json()) == decision
    resumed = await continue_run(registry, store, paused.run_id, decisions=(decision,))
    assert resumed.status == "review"  # Approval of first does not approve second.
    assert resumed.state.result.review_queue[0].triggering_result.capability_id == "second.describe"
    assert resumed.state.result.review_queue[0].strand_set.get("middle.id").confidence == 0.4
    assert resumed.state.review_decisions[0]["observation"]["status"] == "ambiguous"
    finished = await continue_run(
        registry, store, paused.run_id, decisions=(ReviewDecision(key, "accept"),)
    )
    assert finished.status == "complete"
    assert finished.state.result.resolved[0].get("output.id").value == "chosen"
    assert registry.get_weaver("first").batch_calls == 1
    assert registry.get_weaver("second").batch_calls == 1


async def test_duplicate_rows_partial_decision_and_rejection(tmp_path):
    registry = _registry()
    prepared = prepare_query(
        registry, QueryRequest((_input(row=1), _input(row=2)), frozenset({"output.id"}))
    )
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    paused = await start_run(registry, prepared, store)
    first, second = paused.state.result.review_queue
    assert first.strand_set.execution_key != second.strand_set.execution_key
    partial = await continue_run(
        registry,
        store,
        paused.run_id,
        decisions=(ReviewDecision(first.strand_set.execution_key, "select", 1),),
    )
    assert partial.status == "review" and len(partial.state.result.resolved) == 1
    assert partial.state.result.resolved[0].source_row == 1
    finished = await continue_run(
        registry,
        store,
        paused.run_id,
        decisions=(ReviewDecision(second.strand_set.execution_key, "reject"),),
    )
    assert finished.status == "complete" and len(finished.state.result.unresolved) == 1
    assert finished.state.result.unresolved[0][0].source_row == 2


async def test_review_in_repeated_traversal_never_restarts_completed_fan(tmp_path):
    registry = BraidRegistry()
    calls = []

    def fan(ss, backend, outputs):
        value = str(ss.get(GENE).value)
        calls.append(value)
        if value == "7157":
            return WeaveResult(
                ORTHOLOGS,
                "1.0.0",
                backend,
                frozenset({"g"}),
                WeaveStatus.AMBIGUOUS,
                candidates=(CandidateResult((Strand(GENE, "100"),), 0.9),),
            )
        return _ortholog_result(["200", "300"])

    registry.register(ScriptedWeaver(fan, capability=_orthologs_cap(), weaver_id="ncbi"))
    describe = simple_capability("describe", {GENE}, {SYMBOL})
    registry.register(
        ScriptedWeaver(
            lambda ss, b, out: WeaveResult(
                describe.id,
                "1.0.0",
                b,
                frozenset({"g"}),
                WeaveStatus.OK,
                strands=(Strand(SYMBOL, "SYM-" + str(ss.get(GENE).value)),),
            ),
            capability=describe,
            weaver_id="desc",
        )
    )
    inputs = tuple(StrandSet.from_strands("same", [Strand(GENE, "7157")]) for _ in range(2))
    for row, ss in enumerate(inputs, 1):
        ss.source_row = row
    prepared = prepare_query(
        registry,
        QueryRequest(
            inputs,
            frozenset({SYMBOL}),
            (ORTHOLOGS, ORTHOLOGS),
            options=QueryOptions(expand_policy=ExpandPolicy.all(), max_expansion=3),
        ),
    )
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    paused = await start_run(registry, prepared, store)
    decisions = tuple(
        ReviewDecision(item.strand_set.execution_key, "select", 0)
        for item in paused.state.result.review_queue
    )
    snapshots = []
    finished = await continue_run(
        registry,
        store,
        paused.run_id,
        decisions=decisions,
        on_saved=lambda cp: snapshots.append(cp.state.to_json()),
    )
    assert finished.status == "complete"
    assert calls == ["7157", "7157", "100"]  # second identical input reuses lookup cache
    assert len(finished.state.result.resolved) == 3
    assert finished.state.result.truncations
    assert {ss.source_row for ss in finished.state.result.resolved} == {1, 2}
    assert all(ss.parent_id == "same" for ss in finished.state.result.resolved)
    for snapshot in snapshots:
        state = QueryExecutionState.from_json(json.loads(json.dumps(snapshot)))
        assert state.to_json() == snapshot
        assert all(frame.budget is state.budget for frame in state.review_continuations)
        from braidworks.core.query_state import continue_query

        await continue_query(registry, state)
        assert state.result.to_json() == finished.state.result.to_json()


async def test_invalid_decisions_are_atomic_and_leave_run_unclaimed(tmp_path):
    registry = _registry()
    prepared = prepare_query(registry, QueryRequest((_input(),), frozenset({"output.id"})))
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    paused = await start_run(registry, prepared, store)
    key = paused.state.result.review_queue[0].strand_set.execution_key
    for decisions in (
        (ReviewDecision("same", "select", 0),),
        (ReviewDecision(key, "select", 99),),
        (ReviewDecision(key, "accept"),),
        (ReviewDecision(key, "select", 0), ReviewDecision(key, "reject")),
    ):
        with pytest.raises(ValueError):
            await continue_run(registry, store, paused.run_id, decisions=decisions)
        assert store.load(paused.run_id).to_json() == paused.to_json()


async def test_legacy_review_without_context_is_not_replayed(tmp_path):
    registry = _registry()
    prepared = prepare_query(registry, QueryRequest((_input(),), frozenset({"output.id"})))
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    paused = await start_run(registry, prepared, store)
    state = QueryExecutionState.from_json(paused.state.to_json())
    state.result.review_queue[0].continuation = {}
    with pytest.raises(ValueError, match="Legacy review"):
        apply_review_decisions(
            registry,
            state,
            (ReviewDecision(state.result.review_queue[0].strand_set.execution_key, "select", 0),),
        )


async def test_review_keeps_unapplied_parallel_sibling(tmp_path):
    registry = _registry()
    sibling = simple_capability("sibling.lookup", {"input.id"}, {"side.id"})
    registry.register(
        ScriptedWeaver(
            lambda ss, b, out: WeaveResult(
                sibling.id,
                "1.0.0",
                b,
                frozenset({"g"}),
                WeaveStatus.OK,
                strands=(Strand("side.id", "side"),),
            ),
            capability=sibling,
            weaver_id="sibling",
        )
    )
    prepared = prepare_query(
        registry, QueryRequest((_input(),), frozenset({"output.id", "side.id"}))
    )
    from dataclasses import replace

    from braidworks.core import Braid

    original, indices = prepared.plans[0]
    steps = {step.capability_id: step for step in original.steps}
    braid = Braid(
        tuple(steps[cid] for cid in ("first.resolve", "sibling.lookup", "second.describe")),
        original.from_types,
        original.to_types,
    )
    prepared = replace(prepared, plans=((braid, indices),))
    assert len(prepared.plans[0][0].waves()[0]) == 2
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    paused = await start_run(registry, prepared, store)
    item = paused.state.result.review_queue[0]
    assert "sibling.lookup" in {step.capability_id for step in item.remaining_steps}
    finished = await continue_run(
        registry,
        store,
        paused.run_id,
        decisions=(ReviewDecision(item.strand_set.execution_key, "select", 0),),
    )
    row = finished.state.result.resolved[0]
    assert row.get("side.id").value == "side"
    assert row.get("output.id").value == "chosen"
    assert registry.get_weaver("first").batch_calls == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"entity_key": "", "action": "accept"},
        {"entity_key": "node:0", "action": "select"},
        {"entity_key": "node:0", "action": "select", "candidate_index": True},
        {"entity_key": "node:0", "action": "accept", "candidate_index": 0},
    ],
)
def test_invalid_decision_values(kwargs):
    with pytest.raises(ValueError):
        ReviewDecision(**kwargs)


async def test_review_preserves_earlier_branch_errors(tmp_path):
    from dataclasses import replace

    from braidworks.core import Braid

    registry = _registry()
    failed = simple_capability("failed.lookup", {"input.id"}, {"failed.id"})
    registry.register(
        ScriptedWeaver(
            lambda ss, b, out: WeaveResult(
                failed.id, "1.0.0", b, frozenset({"g"}), WeaveStatus.ERROR, errors=("503 upstream",)
            ),
            capability=failed,
            weaver_id="failed",
        )
    )
    prepared = prepare_query(
        registry, QueryRequest((_input(),), frozenset({"output.id", "failed.id"}))
    )
    braid, indices = prepared.plans[0]
    steps = {step.capability_id: step for step in braid.steps}
    prepared = replace(
        prepared,
        plans=(
            (
                Braid(
                    tuple(
                        steps[cid] for cid in ("failed.lookup", "first.resolve", "second.describe")
                    ),
                    braid.from_types,
                    braid.to_types,
                ),
                indices,
            ),
        ),
    )
    store = SQLiteRunStore(tmp_path / "runs.sqlite")
    paused = await start_run(registry, prepared, store)
    item = paused.state.result.review_queue[0]
    assert item.continuation["prior_errors"] == [["failed", "failed.lookup"]]
    decision = ReviewDecision(item.strand_set.execution_key, "select", 0)
    state = apply_review_decisions(registry, paused.state, (decision,))
    frame = state.review_continuations[0]
    assert all(
        errors == [["failed", "failed.lookup"]]
        for errors in frame.active.settings["prior_errors"].values()
    )
    finished = await continue_run(registry, store, paused.run_id, decisions=(decision,))
    assert finished.status == "complete"
    assert finished.state.result.errors and not finished.state.result.fatal_errors()
    assert registry.get_weaver("failed").batch_calls == 1
