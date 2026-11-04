"""View discovery preserves tolerant presentation over shared mechanics."""

import pytest
from weaverkit.view import discover_registry


def test_tolerant_view_uses_shared_filter_and_keeps_problem_text(monkeypatch):
    from types import SimpleNamespace

    from braidworks.core import discovery as core_discovery

    def bad():
        raise ImportError("dependency missing")

    def excluded():
        pytest.fail("excluded view plugin imported")

    monkeypatch.setattr(
        core_discovery,
        "entry_points",
        lambda **_: [
            SimpleNamespace(name="bad", value="bad:build", load=bad),
            SimpleNamespace(name="excluded", load=excluded),
        ],
    )
    report = discover_registry(only=frozenset({"bad"}))
    assert report.registry.manifests() == ()
    assert report.problems == ["bad: ImportError: dependency missing"]
