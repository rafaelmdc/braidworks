"""BraidRegistry: registration, manifest validation, graph projection."""

from __future__ import annotations

import pytest

from braidworks.core.capability import Capability, OutputGroup
from braidworks.core.exceptions import InvalidManifestError
from braidworks.core.registry import BraidRegistry

from helpers import make_weaver, resolve_name_capability, simple_capability


def test_two_weavers_both_appear_in_manifests():
    reg = BraidRegistry()
    reg.register(make_weaver(resolve_name_capability(), weaver_id="ncbi"))
    reg.register(
        make_weaver(simple_capability("up.cap", {"a"}, {"b"}), weaver_id="uniprot")
    )
    ids = {m.weaver_id for m in reg.manifests()}
    assert ids == {"ncbi", "uniprot"}


def test_multi_input_capability_registered_but_not_an_edge():
    reg = BraidRegistry()
    multi = simple_capability("m.cap", {"a", "b"}, {"c"})
    reg.register(make_weaver(multi, weaver_id="m"))
    graph = reg.build_graph()
    # Registered...
    assert reg.get_capability("m", "m.cap") is multi
    # ...but no edge produces "c" because multi-input capabilities are not projected.
    assert "c" not in graph


def test_empty_weaver_id_rejected():
    reg = BraidRegistry()
    with pytest.raises(InvalidManifestError):
        reg.register(make_weaver(resolve_name_capability(), weaver_id=""))


def test_produce_type_in_two_groups_rejected():
    cap = Capability(
        id="bad",
        consumes=frozenset({"a"}),
        produces=frozenset({"x", "y"}),
        output_groups=(
            OutputGroup(id="g1", outputs=frozenset({"x", "y"})),
            OutputGroup(id="g2", outputs=frozenset({"y"})),  # y overlaps g1
        ),
        backends=("local",),
    )
    reg = BraidRegistry()
    with pytest.raises(InvalidManifestError):
        reg.register(make_weaver(cap, weaver_id="w"))


def test_produce_type_in_no_group_rejected():
    cap = Capability(
        id="bad",
        consumes=frozenset({"a"}),
        produces=frozenset({"x", "y"}),
        output_groups=(OutputGroup(id="g1", outputs=frozenset({"x"})),),  # y orphaned
        backends=("local",),
    )
    reg = BraidRegistry()
    with pytest.raises(InvalidManifestError):
        reg.register(make_weaver(cap, weaver_id="w"))


def test_duplicate_group_ids_rejected():
    cap = Capability(
        id="bad",
        consumes=frozenset({"a"}),
        produces=frozenset({"x", "y"}),
        output_groups=(
            OutputGroup(id="g", outputs=frozenset({"x"})),
            OutputGroup(id="g", outputs=frozenset({"y"})),  # duplicate id
        ),
        backends=("local",),
    )
    reg = BraidRegistry()
    with pytest.raises(InvalidManifestError):
        reg.register(make_weaver(cap, weaver_id="w"))


def test_max_batch_size_zero_rejected():
    cap = simple_capability("z.cap", {"a"}, {"b"}, max_batch_size=0)
    reg = BraidRegistry()
    with pytest.raises(InvalidManifestError):
        reg.register(make_weaver(cap, weaver_id="w"))


def test_parallel_edges_kept_lower_cost_routes():
    """Interchangeable sources for the same A→B edge are both retained (a multigraph);
    routing takes the cheaper one, but the alternate survives for reroute fallback."""
    from braidworks.core.planner import Braider

    reg = BraidRegistry()
    reg.register(make_weaver(simple_capability("c.hi", {"a"}, {"b"}, cost=5.0), weaver_id="hi"))
    reg.register(make_weaver(simple_capability("c.lo", {"a"}, {"b"}, cost=1.0), weaver_id="lo"))
    graph = reg.build_graph()
    # both parallel edges are present (not collapsed)
    caps = {d["capability_id"] for d in graph.get_edge_data("a", "b").values()}
    assert caps == {"c.hi", "c.lo"}
    # the planner still picks the cheapest as the primary route
    braid = Braider(reg).plan(frozenset({"a"}), frozenset({"b"}))
    assert braid.steps[0].capability_id == "c.lo"
