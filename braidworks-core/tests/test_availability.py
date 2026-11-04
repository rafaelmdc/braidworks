"""Disabled declarations explain failed routes without changing active execution."""

from dataclasses import replace

import pytest
from braidworks.core.availability import require_capability
from braidworks.core.braid import BackendPolicy
from braidworks.core.exceptions import (
    BackendUnavailable,
    InvalidManifestError,
    NoPathError,
    NoPlanError,
    UnsupportedCapability,
)
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry
from helpers import FakeWeaver, manifest, simple_capability


def catalogue(*, enabled=False):
    first = simple_capability("first", {"a"}, {"b"})
    last = simple_capability("last", {"b"}, {"c"}, backends=("api",))
    full = manifest(first, last, weaver_id="source")
    active = full if enabled else replace(full, capabilities=(first,))
    weaver = FakeWeaver(active)
    weaver.declared_manifest = lambda: full
    return weaver


def registry(weaver):
    result = BraidRegistry()
    result.register(weaver)
    return result


def test_catalogue_does_not_change_active_graph_or_inventory():
    reg = registry(catalogue())
    assert "c" not in reg.build_graph()
    assert "c" in reg.build_graph(declared=True)
    assert len(reg.manifests()[0].capabilities) == 1
    assert "c" not in reg.build_graph()


@pytest.mark.parametrize("source", ["a", "b"])
def test_disabled_route_names_connecting_capability(source):
    with pytest.raises(NoPlanError, match="source / last.*not enabled: api"):
        Braider(registry(catalogue())).plan(frozenset({source}), frozenset({"c"}))


@pytest.mark.parametrize(
    "source,target,exclude",
    [
        ("unrelated", "c", frozenset()),
        ("a", "unknown", frozenset()),
        ("a", "c", frozenset({("source", "last")})),
    ],
)
def test_disconnected_unknown_and_excluded_stay_no_path(source, target, exclude):
    with pytest.raises(NoPathError):
        Braider(registry(catalogue())).plan(
            frozenset({source}), frozenset({target}), exclude=exclude
        )


def test_policy_block_and_successful_assignment():
    planner = Braider(registry(catalogue(enabled=True)))
    with pytest.raises(NoPlanError, match="source / last.*enabled: api"):
        planner.plan(frozenset({"a"}), frozenset({"c"}), backend_policy=BackendPolicy.LOCAL_ONLY)
    assert [s.primary_backend for s in planner.plan(frozenset({"a"}), frozenset({"c"})).steps] == [
        "local",
        "api",
    ]
    assert planner.plan(frozenset({"c"}), frozenset({"c"})).steps == ()


def test_direct_and_explicit_capability_diagnostics():
    weaver = catalogue()
    with pytest.raises(BackendUnavailable, match="not enabled"):
        require_capability(weaver, "last")
    with pytest.raises(BackendUnavailable, match="not supported"):
        require_capability(weaver, "first", "api")
    with pytest.raises(UnsupportedCapability):
        require_capability(weaver, "unknown")
    with pytest.raises(NoPlanError, match="not enabled"):
        Braider(registry(weaver)).plan_capability("source", "last")


@pytest.mark.parametrize("change", ["version", "shape", "backend"])
def test_mismatched_catalogue_rejected(change):
    weaver = catalogue()
    full = weaver.declared_manifest()
    if change == "version":
        full = replace(full, version="2")
    else:
        cap = full.capabilities[0]
        cap = replace(cap, cost=99) if change == "shape" else replace(cap, backends=("api",))
        full = replace(full, capabilities=(cap, *full.capabilities[1:]))
    weaver.declared_manifest = lambda: full
    with pytest.raises(InvalidManifestError):
        registry(weaver)


def test_cli_disabled_capability_reports_backend(monkeypatch, capsys):
    from braidworks.core import cli

    monkeypatch.setattr(cli, "_load_registry", lambda only: registry(catalogue()))
    assert cli.main(["run", "source", "last", "--have", "b=value"]) == 1
    assert "not enabled" in capsys.readouterr().err


def test_alternative_input_and_conjunction_follow_graph_rules():
    weaver = catalogue()
    full = weaver.declared_manifest()
    last = replace(
        full.capabilities[1], consumes=frozenset({"b", "alternative"}), consumes_any=True
    )
    weaver.declared_manifest = lambda: replace(full, capabilities=(full.capabilities[0], last))
    with pytest.raises(NoPlanError):
        Braider(registry(weaver)).plan(frozenset({"alternative"}), frozenset({"c"}))
    last = replace(last, consumes_any=False)
    with pytest.raises(NoPathError):
        Braider(registry(weaver)).plan(frozenset({"b", "alternative"}), frozenset({"c"}))


def test_enabled_alternative_wins_without_diagnostics():
    reg = registry(catalogue())
    reg.register(
        FakeWeaver(manifest(simple_capability("alternative", {"a"}, {"c"}), weaver_id="other"))
    )
    assert Braider(reg).plan(frozenset({"a"}), frozenset({"c"})).steps[0].weaver_id == "other"


@pytest.mark.parametrize('token', ['last', 'source.last'])
def test_disabled_explicit_traversal_keeps_backend_context(token):
    from braidworks.core.traverse import resolve_traversal

    weaver = catalogue()
    full = weaver.declared_manifest()
    last = replace(full.capabilities[1], set_outputs=frozenset({'c'}))
    weaver.declared_manifest = lambda: replace(full, capabilities=(full.capabilities[0], last))
    with pytest.raises(NoPlanError, match='not enabled'):
        resolve_traversal(registry(weaver), token)
