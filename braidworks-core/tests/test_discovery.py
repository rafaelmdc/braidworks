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
