import json

import pytest
from braidworks.core import PreparedQuery, QueryOptions, QueryRequest, execute_query, prepare_query
from braidworks.core.exceptions import NoPathError
from braidworks.core.query import normalize_expansion
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand, StrandSet
from helpers import ScriptedWeaver, simple_capability


def _registry():
    registry = BraidRegistry()
    for letter in ("a", "b"):
        cap = simple_capability(f"{letter}.lookup", {f"input.{letter}"}, {"output.value"})

        def resolve(ss, backend, outputs, letter=letter):
            return WeaveResult(
                f"{letter}.lookup",
                "1.0.0",
                backend,
                frozenset({"g"}),
                WeaveStatus.OK,
                strands=(Strand("output.value", letter),),
            )

        registry.register(ScriptedWeaver(resolve, capability=cap, weaver_id=letter))
    return registry


def _input(letter, row):
    ss = StrandSet.from_strands("duplicate", [Strand(f"input.{letter}", "value")])
    ss.source_row = row
    return ss


async def test_json_preparation_preserves_duplicates_and_caller_state():
    registry = _registry()
    inputs = (_input("a", 1), _input("b", 2), _input("a", 3))
    request = QueryRequest(inputs, frozenset({"output.value"}))
    original = request.to_json()
    prepared = prepare_query(registry, request)
    restored = PreparedQuery.from_json(json.loads(json.dumps(prepared.to_json())))
    assert restored.to_json() == prepared.to_json()
    result = await execute_query(registry, restored)
    assert sorted(ss.source_row for ss in result.resolved) == [1, 2, 3]
    assert [ss.entity_id for ss in result.resolved] == ["duplicate"] * 3
    assert request.to_json() == original
    assert all(ss.get("output.value") is None for ss in inputs)


def test_all_groups_preflight_before_calls():
    registry = _registry()
    request = QueryRequest((_input("a", 1), _input("missing", 2)), frozenset({"output.value"}))
    with pytest.raises(NoPathError):
        prepare_query(registry, request)
    assert registry.get_weaver("a").batch_calls == 0


@pytest.mark.parametrize(
    "mode,k,expected",
    [("none", 1, "top"), ("top:2", 1, "top_k"), ("top_k", 2, "top_k"), ("all", 1, "all")],
)
def test_expansion_spellings(mode, k, expected):
    assert normalize_expansion(mode, k).mode.value == expected
    options = QueryOptions(expand_policy=normalize_expansion(mode, k))
    assert QueryOptions.from_json(options.to_json()) == options
    assert normalize_expansion(None, traversal=True).mode.value == "all"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_confidence_before_sources(value):
    with pytest.raises(ValueError):
        QueryOptions(confidence_threshold=value)


@pytest.mark.parametrize("mode,k", [("mystery", 1), ("top:bad", 1), ("top_k", 0), ("top_k", True)])
def test_invalid_expansion_before_sources(mode, k):
    with pytest.raises(ValueError):
        normalize_expansion(mode, k)
