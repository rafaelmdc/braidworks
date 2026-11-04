"""Worker registry discovery via the ``braidworks.weavers`` entry-point group."""

from __future__ import annotations

import pytest
from braidworks_arq import discovery
from braidworks_arq.settings import queue_for
from fakes import EchoWeaver, registry_with


def test_queue_name_is_per_weaver():
    assert queue_for("ncbi") == "weaver.ncbi"
    assert queue_for("disbiome") == "weaver.disbiome"


def test_set_and_get_registry_roundtrips():
    reg = registry_with(EchoWeaver())
    discovery.set_registry(reg)
    assert discovery.get_registry() is reg


def test_only_filter_restricts_built_registry():
    reg = discovery.build_registry_from_entry_points(only=frozenset({"definitely-not-installed"}))
    assert reg.manifests() == ()


def test_installed_weavers_are_discoverable():
    names = {name for name, _ in discovery.iter_weaver_builders()}
    if not names:
        pytest.skip("no braidworks.weavers entry points installed in this environment")
    reg = discovery.build_registry_from_entry_points()
    discovered = {m.weaver_id for m in reg.manifests()}
    assert discovered <= names
    assert {"ncbi", "bacdive", "disbiome"} & names, names


def test_worker_cache_lifetime_remains_local(monkeypatch):
    built = []

    def build():
        registry = registry_with(EchoWeaver())
        built.append(registry)
        return registry

    monkeypatch.setattr(discovery, "build_registry_from_entry_points", build)
    discovery.set_registry(None)
    try:
        first = discovery.get_registry()
        assert discovery.get_registry() is first
        assert len(built) == 1
        discovery.set_registry(None)
        assert discovery.get_registry() is not first
        assert len(built) == 2
    finally:
        discovery.set_registry(None)
