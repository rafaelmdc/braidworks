"""Discovery must filter metadata before importing optional plugins."""

from types import SimpleNamespace

import pytest
from braidworks.core import discovery
from helpers import ScriptedWeaver


@pytest.mark.parametrize("only", [frozenset({"ncbi"}), frozenset()])
def test_excluded_entry_point_is_never_loaded(monkeypatch, only):
    loaded = []

    def broken_load():
        loaded.append("broken")
        raise ImportError("optional dependency missing")

    def selected_load():
        loaded.append("ncbi")
        return lambda: ScriptedWeaver(lambda *_: None)

    monkeypatch.setattr(
        discovery,
        "entry_points",
        lambda **_: [
            SimpleNamespace(name="broken", load=broken_load),
            SimpleNamespace(name="ncbi", load=selected_load),
        ],
    )
    discovery.build_registry_from_entry_points(only=only)
    assert loaded == (["ncbi"] if only else [])


def test_selected_broken_entry_point_reports_import_failure(monkeypatch):
    def broken_load():
        raise ImportError("optional dependency missing")

    monkeypatch.setattr(
        discovery,
        "entry_points",
        lambda **_: [SimpleNamespace(name="broken", load=broken_load)],
    )
    with pytest.raises(ImportError, match="optional dependency missing"):
        discovery.build_registry_from_entry_points(only=frozenset({"broken"}))


@pytest.mark.parametrize("policy", list(discovery.DiscoveryPolicy))
def test_shared_discovery_filters_before_import(monkeypatch, policy):
    def excluded():
        pytest.fail("excluded plugin imported")

    monkeypatch.setattr(
        discovery,
        "entry_points",
        lambda **_: [
            SimpleNamespace(name="excluded", load=excluded),
            SimpleNamespace(name="ncbi", load=lambda: lambda: ScriptedWeaver(lambda *_: None)),
        ],
    )
    report = discovery.discover_registry(only=frozenset({"ncbi"}), policy=policy)
    assert [manifest.weaver_id for manifest in report.registry.manifests()] == ["ncbi"]
    assert report.failures == ()
    assert discovery.discover_registry(only=frozenset(), policy=policy).registry.manifests() == ()


@pytest.mark.parametrize("stage", ["load", "build", "register"])
def test_tolerant_discovery_reports_stage_and_keeps_valid_plugin(monkeypatch, stage):
    def fail():
        raise RuntimeError("plugin failed")

    good = lambda: ScriptedWeaver(lambda *_: None)
    if stage == "load":
        load = fail
    elif stage == "build":
        load = lambda: fail
    else:
        # Duplicate valid manifests fail registration after the first one succeeds.
        load = lambda: good
    monkeypatch.setattr(
        discovery,
        "entry_points",
        lambda **_: [
            SimpleNamespace(name="good", value="good:build", load=lambda: good),
            SimpleNamespace(name="bad", value="bad:build", load=load),
            SimpleNamespace(
                name="later",
                value="later:build",
                load=lambda: lambda: ScriptedWeaver(lambda *_: None, weaver_id="later"),
            ),
        ],
    )
    report = discovery.discover_registry(policy=discovery.DiscoveryPolicy.TOLERANT)
    assert {m.weaver_id for m in report.registry.manifests()} == {"ncbi", "later"}
    assert len(report.failures) == 1
    failure = report.failures[0]
    assert (failure.name, failure.value, failure.stage) == ("bad", "bad:build", stage)
    assert failure.exception_type == (
        "InvalidManifestError" if stage == "register" else "RuntimeError"
    )
    assert discovery.DiscoveryFailure.from_json(failure.to_json()) == failure


@pytest.mark.parametrize("stage", ["load", "build", "register"])
def test_strict_discovery_preserves_exception_and_adds_context(monkeypatch, stage):
    original = RuntimeError("same exception")

    def fail(*args):
        raise original

    load = fail if stage == "load" else lambda: fail if stage == "build" else lambda: object()
    monkeypatch.setattr(
        discovery,
        "entry_points",
        lambda **_: [
            SimpleNamespace(name="broken", value="broken:build", load=load),
        ],
    )
    if stage == "register":
        monkeypatch.setattr(discovery.BraidRegistry, "register", fail)
    with pytest.raises(RuntimeError) as caught:
        discovery.build_registry_from_entry_points()
    assert caught.value is original
    assert any("broken" in note and f"stage={stage}" in note for note in original.__notes__)


def test_tolerant_does_not_swallow_process_control_or_enumeration_failure(monkeypatch):
    def interrupt():
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        discovery, "entry_points", lambda **_: [SimpleNamespace(name="stop", load=interrupt)]
    )
    with pytest.raises(KeyboardInterrupt):
        discovery.discover_registry(policy=discovery.DiscoveryPolicy.TOLERANT)

    def metadata_failure(**kwargs):
        raise RuntimeError("metadata failed")

    monkeypatch.setattr(discovery, "entry_points", metadata_failure)
    with pytest.raises(RuntimeError, match="metadata failed"):
        discovery.discover_registry(policy=discovery.DiscoveryPolicy.TOLERANT)


def test_invalid_policy_is_rejected_before_discovery(monkeypatch):
    monkeypatch.setattr(discovery, "entry_points", lambda **_: pytest.fail("enumerated metadata"))
    with pytest.raises(ValueError):
        discovery.discover_registry(policy="typo")


def test_discovery_builds_fresh_registries(monkeypatch):
    monkeypatch.setattr(discovery, "entry_points", lambda **_: [])
    assert discovery.discover_registry().registry is not discovery.discover_registry().registry
