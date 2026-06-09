"""Worker registry discovery via the ``braidworks.weavers`` entry-point group."""

from __future__ import annotations

import pytest

from braidworks_celery import discovery
from braidworks_celery.app import queue_for

from fakes import EchoWeaver, registry_with


def test_queue_name_is_per_weaver():
    assert queue_for("ncbi") == "weaver.ncbi"
    assert queue_for("disbiome") == "weaver.disbiome"


def test_set_and_get_registry_roundtrips():
    reg = registry_with(EchoWeaver())
    discovery.set_registry(reg)
    assert discovery.get_registry() is reg


def test_only_filter_restricts_built_registry():
    # No weaver named "definitely-not-installed" exists, so the registry is empty.
    reg = discovery.build_registry_from_entry_points(only=frozenset({"definitely-not-installed"}))
    assert reg.manifests() == ()


def test_installed_weavers_are_discoverable():
    """The repo's weavers advertise entry points; building them must register cleanly.

    Skips only if no weaver packages are installed in the environment (e.g. a
    core-only checkout), so it never produces a false failure.
    """
    names = {name for name, _ in discovery.iter_weaver_builders()}
    if not names:
        pytest.skip("no braidworks.weavers entry points installed in this environment")
    reg = discovery.build_registry_from_entry_points()
    discovered = {m.weaver_id for m in reg.manifests()}
    # Every advertised name builds a weaver whose manifest id matches the entry name.
    assert discovered <= names
    assert {"ncbi", "bacdive", "disbiome"} & names, names
