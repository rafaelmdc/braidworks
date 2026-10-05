"""Query-level continuation equivalence across groups, phases, review and reroutes."""

import json

import pytest
from braidworks.core import QueryOptions, QueryRequest, execute_query, prepare_query
from braidworks.core.executor import ExpandPolicy
from braidworks.core.query_state import QueryExecutionState, continue_query
from test_error_tolerance import _input as reroute_input
from test_error_tolerance import _reroute_registry
from test_query import _input as mixed_input
from test_query import _registry as mixed_registry
from test_traverse import SYMBOL
from test_traverse import _inputs as fan_inputs
from test_traverse import _registry as fan_registry


@pytest.mark.parametrize("scenario", ["mixed", "traversal", "reroute"])
async def test_restore_at_every_query_checkpoint(scenario):
    if scenario == "mixed":
        registry = mixed_registry()
        request = QueryRequest(
            (mixed_input("a", 1), mixed_input("b", 2), mixed_input("a", 3)),
            frozenset({"output.value"}),
        )
    elif scenario == "traversal":
        registry = fan_registry()
        inputs = fan_inputs("7157") + fan_inputs("7157")
        for i, ss in enumerate(inputs, 1):
            ss.source_row = i
        request = QueryRequest(
            tuple(inputs),
            frozenset({SYMBOL}),
            ("ncbi.list_orthologs", "ncbi.list_orthologs"),
            options=QueryOptions(expand_policy=ExpandPolicy.all(), max_expansion=4),
        )
    else:
        registry = _reroute_registry()
        request = QueryRequest(tuple(reroute_input() + reroute_input()), frozenset({"c"}))
    prepared = prepare_query(registry, request)
    snapshots = []
    expected = await execute_query(
        registry,
        prepared,
        on_checkpoint=lambda state: snapshots.append(json.loads(json.dumps(state.to_json()))),
    )
    for snapshot in snapshots:
        state = QueryExecutionState.from_json(snapshot)
        assert state.to_json() == snapshot
        actual = await continue_query(registry, state)
        assert actual.to_json() == expected.to_json()
        assert actual.total() == expected.total()
        assert len(actual.fatal_errors()) == len(expected.fatal_errors())


async def test_completed_query_does_not_restart_source():
    registry = mixed_registry()
    prepared = prepare_query(
        registry, QueryRequest((mixed_input("a", 1),), frozenset({"output.value"}))
    )
    snapshots = []
    await execute_query(
        registry, prepared, on_checkpoint=lambda state: snapshots.append(state.to_json())
    )
    calls = registry.get_weaver("a").batch_calls
    await continue_query(registry, QueryExecutionState.from_json(snapshots[-1]))
    assert registry.get_weaver("a").batch_calls == calls


@pytest.mark.parametrize("status", ["no_match", "error", "ambiguous"])
async def test_terminal_failures_review_and_duplicates_restore(status):
    from braidworks.core.registry import BraidRegistry
    from braidworks.core.result import CandidateResult, WeaveResult, WeaveStatus
    from braidworks.core.strand import Strand, StrandSet
    from helpers import ScriptedWeaver, simple_capability

    cap = simple_capability("source.resolve", {"input.id"}, {"output.value"})
    registry = BraidRegistry()

    def resolve(ss, backend, outputs):
        return WeaveResult(
            cap.id,
            "1.0.0",
            backend,
            frozenset({"g"}),
            WeaveStatus(status),
            candidates=(CandidateResult((Strand("output.value", "candidate"),), 0.9),)
            if status == "ambiguous"
            else (),
            errors=("503 upstream",) if status == "error" else (),
        )

    registry.register(ScriptedWeaver(resolve, capability=cap, weaver_id="source"))
    inputs = [StrandSet.from_strands("same", [Strand("input.id", "x")]) for _ in range(2)]
    prepared = prepare_query(registry, QueryRequest(tuple(inputs), frozenset({"output.value"})))
    snapshots = []
    expected = await execute_query(
        registry, prepared, on_checkpoint=lambda state: snapshots.append(state.to_json())
    )
    for snapshot in snapshots:
        actual = await continue_query(registry, QueryExecutionState.from_json(snapshot))
        assert actual.to_json() == expected.to_json()
        assert actual.total() == 2
