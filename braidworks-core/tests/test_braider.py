"""Braider: routing, coalescing, dependency ordering, backend assignment."""

from __future__ import annotations

import pytest
from braidworks.core.braid import BackendPolicy, FallbackCondition
from braidworks.core.exceptions import NoPathError, NoPlanError
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from helpers import make_weaver, resolve_name_capability, simple_capability


def _registry(*weavers) -> BraidRegistry:
    reg = BraidRegistry()
    for w in weavers:
        reg.register(w)
    return reg


def test_single_step_braid():
    reg = _registry(make_weaver(resolve_name_capability(), weaver_id="ncbi"))
    braid = Braider(reg).plan(frozenset({"organism.name"}), frozenset({"ncbi.taxon.id"}))
    assert len(braid.steps) == 1
    assert braid.steps[0].capability_id == "ncbi.resolve_name"
    assert braid.from_types == frozenset({"organism.name"})
    assert braid.to_types == frozenset({"ncbi.taxon.id"})


def test_from_types_is_minimal_not_all_available():
    reg = _registry(make_weaver(resolve_name_capability(), weaver_id="ncbi"))
    braid = Braider(reg).plan(
        frozenset({"organism.name", "sample.id", "extra"}),
        frozenset({"ncbi.taxon.id"}),
    )
    assert braid.steps[0].input_types == frozenset({"organism.name"})
    assert braid.from_types == frozenset({"organism.name"})  # not the extras


def test_outputs_coalesce_into_single_invocation():
    reg = _registry(make_weaver(resolve_name_capability(), weaver_id="ncbi"))
    targets = frozenset({"ncbi.taxon.id", "ncbi.taxon.lineage", "ncbi.taxon.rank"})
    braid = Braider(reg).plan(frozenset({"organism.name"}), targets)
    assert len(braid.steps) == 1
    assert braid.steps[0].output_types == targets


def test_two_hop_path_ordered_by_dependency():
    chain = make_weaver(
        simple_capability("c.name2id", {"organism.name"}, {"ncbi.taxon.id"}),
        simple_capability("c.id2proteome", {"ncbi.taxon.id"}, {"uniprot.proteome.id"}),
        weaver_id="chain",
    )
    reg = _registry(chain)
    braid = Braider(reg).plan(
        frozenset({"organism.name"}), frozenset({"uniprot.proteome.id"})
    )
    assert [s.capability_id for s in braid.steps] == ["c.name2id", "c.id2proteome"]
    assert braid.from_types == frozenset({"organism.name"})
    assert braid.to_types == frozenset({"uniprot.proteome.id"})


def test_unproducible_target_raises_no_path():
    reg = _registry(make_weaver(resolve_name_capability(), weaver_id="ncbi"))
    with pytest.raises(NoPathError):
        Braider(reg).plan(frozenset({"organism.name"}), frozenset({"nonexistent.type"}))


def test_already_available_target_produces_no_steps():
    reg = _registry(make_weaver(resolve_name_capability(), weaver_id="ncbi"))
    braid = Braider(reg).plan(
        frozenset({"organism.name", "ncbi.taxon.id"}), frozenset({"ncbi.taxon.id"})
    )
    assert braid.steps == ()
    assert braid.from_types == frozenset()


def test_local_first_with_both_backends():
    reg = _registry(
        make_weaver(simple_capability("c", {"a"}, {"b"}, backends=("local", "api")), weaver_id="w")
    )
    braid = Braider(reg).plan(
        frozenset({"a"}), frozenset({"b"}), backend_policy=BackendPolicy.LOCAL_FIRST
    )
    step = braid.steps[0]
    assert step.primary_backend == "local"
    assert step.fallback_backends == ("api",)
    assert step.fallback_on == frozenset(
        {FallbackCondition.NO_MATCH, FallbackCondition.BACKEND_UNAVAILABLE}
    )


def test_local_first_with_api_only_degrades_gracefully():
    reg = _registry(
        make_weaver(simple_capability("c", {"a"}, {"b"}, backends=("api",)), weaver_id="w")
    )
    braid = Braider(reg).plan(
        frozenset({"a"}), frozenset({"b"}), backend_policy=BackendPolicy.LOCAL_FIRST
    )
    step = braid.steps[0]
    assert step.primary_backend == "api"
    assert step.fallback_backends == ()
    assert step.fallback_on == frozenset()  # no fallback backend → no conditions


def test_local_only_with_api_only_raises_no_plan():
    reg = _registry(
        make_weaver(simple_capability("c", {"a"}, {"b"}, backends=("api",)), weaver_id="w")
    )
    with pytest.raises(NoPlanError):
        Braider(reg).plan(
            frozenset({"a"}), frozenset({"b"}), backend_policy=BackendPolicy.LOCAL_ONLY
        )


@pytest.mark.parametrize(
    "policy,allowed,blocked",
    [
        (BackendPolicy.LOCAL_ONLY, "local", "api"),
        (BackendPolicy.API_ONLY, "api", "local"),
    ],
)
@pytest.mark.parametrize("multihop", [False, True])
def test_restricted_policy_finds_more_expensive_supported_route(policy, allowed, blocked, multihop):
    supported = [simple_capability("supported", {"a"}, {"b"}, backends=(allowed,), cost=3)]
    if multihop:
        supported = [
            simple_capability("first", {"a"}, {"x"}, backends=(allowed,), cost=2),
            simple_capability("second", {"x"}, {"b"}, backends=(allowed,), cost=2),
        ]
    reg = _registry(
        make_weaver(
            simple_capability("cheap", {"a"}, {"b"}, backends=(blocked,)), weaver_id="cheap"
        ),
        make_weaver(*supported, weaver_id="supported"),
    )
    graph = reg.build_graph()
    edges_before = list(graph.edges(keys=True, data=True))
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"b"}), backend_policy=policy)
    assert [step.capability_id for step in braid.steps] == [cap.id for cap in supported]
    assert all(
        step.primary_backend == allowed and not step.fallback_backends for step in braid.steps
    )
    assert list(reg.build_graph().edges(keys=True, data=True)) == edges_before
    # Unrestricted policies still minimize declared capability cost.
    default = Braider(reg).plan(frozenset({"a"}), frozenset({"b"}))
    assert default.steps[0].weaver_id == "cheap"


def test_policy_pruning_preserves_exclusions_and_no_path_distinction():
    reg = _registry(
        make_weaver(
            simple_capability("cheap", {"a"}, {"b"}, backends=("api",)),
            simple_capability("local", {"a"}, {"b"}, backends=("local",), cost=2),
            weaver_id="w",
        )
    )
    with pytest.raises(NoPlanError, match="local_only"):
        Braider(reg).plan(
            frozenset({"a"}),
            frozenset({"b"}),
            backend_policy=BackendPolicy.LOCAL_ONLY,
            exclude=frozenset({("w", "local")}),
        )
    with pytest.raises(NoPathError):
        Braider(reg).plan(
            frozenset({"a"}),
            frozenset({"b"}),
            backend_policy=BackendPolicy.LOCAL_ONLY,
            exclude=frozenset({("w", "local"), ("w", "cheap")}),
        )
    with pytest.raises(NoPathError):
        Braider(reg).plan(
            frozenset({"a"}), frozenset({"absent"}), backend_policy=BackendPolicy.LOCAL_ONLY
        )


def test_multi_input_capability_not_reachable():
    reg = _registry(make_weaver(simple_capability("m", {"a", "b"}, {"c"}), weaver_id="m"))
    with pytest.raises(NoPathError):
        Braider(reg).plan(frozenset({"a", "b"}), frozenset({"c"}))
