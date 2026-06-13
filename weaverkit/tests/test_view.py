"""Tests for ``weaverkit view`` — network + path projection and HTML rendering.

These build a registry from tiny in-test weavers (no entry-point discovery, no
network) so the projection logic is exercised deterministically. ``discover_registry``
itself is smoke-tested against whatever is installed.
"""

from __future__ import annotations

import json

import pytest
from braidworks.core.braid import BackendPolicy
from braidworks.core.capability import Capability, OutputGroup, WeaverManifest
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import StrandSet
from braidworks.core.weaver import BaseWeaver

from weaverkit.view import (
    build_network,
    build_path,
    discover_registry,
    parse_policy,
    render_html,
)


def _weaver(weaver_id, cap_id, consumes, produces, backends):
    manifest = WeaverManifest(
        weaver_id=weaver_id,
        version="0.1.0",
        capabilities=(
            Capability(
                id=cap_id,
                consumes=frozenset(consumes),
                produces=frozenset(produces),
                output_groups=(OutputGroup(id="g", outputs=frozenset(produces)),),
                backends=tuple(backends),
            ),
        ),
    )

    class _W(BaseWeaver):
        MANIFEST = manifest

        def backend_fingerprint(self, backend: str) -> str:
            return f"{weaver_id}-{backend}-v1"

        async def execute(self, capability_id, strand_set, *, requested_outputs, backend):
            return WeaveResult(status=WeaveStatus.NO_MATCH, strand_set=StrandSet(strands=()))

    return _W()


@pytest.fixture
def registry():
    reg = BraidRegistry()
    reg.register(_weaver("alpha", "a1", {"organism.name"}, {"ncbi.taxon.id"}, ("local",)))
    reg.register(
        _weaver("beta", "b1", {"ncbi.taxon.id"}, {"microbe.trait.x"}, ("local", "api"))
    )
    return reg


# --- network -----------------------------------------------------------------


def test_network_is_bipartite_with_weaver_op_nodes(registry):
    net = build_network(registry)
    op_ids = {n["id"] for n in net["nodes"] if n["kind"] == "op"}
    assert op_ids == {"op:alpha:a1", "op:beta:b1"}
    # every edge touches exactly one op node (type -> op or op -> type)
    for e in net["edges"]:
        assert (e["source"] in op_ids) ^ (e["target"] in op_ids)
    assert net["stats"]["weavers"] == 2
    assert net["stats"]["capabilities"] == 2
    assert net["stats"]["types"] == 3  # organism.name, ncbi.taxon.id, microbe.trait.x


def test_network_type_nodes_carry_role_and_label(registry):
    net = build_network(registry)
    types = {n["key"]: n for n in net["nodes"] if n["kind"] == "type"}
    assert types["organism.name"]["role"] == "entry"
    assert types["ncbi.taxon.id"]["role"] == "shared"
    # label is the last two dotted segments
    assert types["ncbi.taxon.id"]["label"] == "taxon.id"


def test_network_weaver_list_has_versions_and_backends(registry):
    net = build_network(registry)
    beta = next(w for w in net["weavers"] if w["id"] == "beta")
    assert beta["version"] == "0.1.0"
    assert beta["backends"] == ["api", "local"]


# --- path --------------------------------------------------------------------


def test_path_projects_the_real_braid(registry):
    path = build_path(
        registry,
        frozenset({"organism.name"}),
        frozenset({"microbe.trait.x"}),
        policy=BackendPolicy.LOCAL_FIRST,
    )
    assert path["step_count"] == 2
    ops = [n for n in path["nodes"] if n["kind"] == "op"]
    assert {o["weaver"] for o in ops} == {"alpha", "beta"}
    # backend policy is reflected on the op nodes
    beta_op = next(o for o in ops if o["weaver"] == "beta")
    assert beta_op["primary_backend"] == "local"
    assert beta_op["fallback_backends"] == ["api"]
    # waves: alpha must run before beta
    assert path["waves"] == [[0], [1]]


# --- policy + render ---------------------------------------------------------


def test_parse_policy_roundtrips_and_rejects_garbage():
    assert parse_policy("api_first") is BackendPolicy.API_FIRST
    with pytest.raises(ValueError):
        parse_policy("nonsense")


def test_render_html_embeds_parseable_json(registry):
    data = {"meta": {"problems": []}, "network": build_network(registry), "paths": []}
    html = render_html(data)
    assert "__BRAIDWORKS_DATA__" not in html  # placeholder fully replaced
    assert "BRAIDWORKS" in html
    # the injected payload is valid JSON we can recover
    marker = "const DATA = "
    start = html.index(marker) + len(marker)
    end = html.index(";\n", start)
    recovered = json.loads(html[start:end])
    assert recovered["network"]["stats"]["weavers"] == 2


# --- discovery (smoke) -------------------------------------------------------


def test_discover_registry_returns_a_registry():
    discovery = discover_registry()
    assert isinstance(discovery.registry, BraidRegistry)
    assert isinstance(discovery.problems, list)
