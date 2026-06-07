"""Consent/auto-setup wiring in build_ncbi_weaver (ensure_taxonomy_db is stubbed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from braidworks.core import BackendConfigurationError
from taxonweaver import factory
from taxonweaver.factory import build_ncbi_weaver
from taxonweaver.setup import default_db_path


@pytest.fixture
def record_ensure(monkeypatch, mini_db_path):
    """Replace ensure_taxonomy_db with a recorder that returns the prebuilt mini DB."""
    calls: list[dict] = []

    def _fake(target, *, auto, refresh=False, **_kwargs):
        calls.append({"target": Path(target), "auto": auto, "refresh": refresh})
        return mini_db_path

    monkeypatch.setattr(factory, "ensure_taxonomy_db", _fake)
    # Hermetic precondition: these tests exercise the "no valid DB yet" path, so
    # don't depend on whether the developer's cache already holds a real default
    # DB (a live E2E run builds one there).
    monkeypatch.setattr(factory, "db_is_valid", lambda *_a, **_k: False)
    return calls


def test_valid_db_path_skips_ensure(monkeypatch, mini_db_path):
    def _boom(*_a, **_k):
        raise AssertionError("ensure_taxonomy_db should not run for a valid DB")

    monkeypatch.setattr(factory, "ensure_taxonomy_db", _boom)
    weaver = build_ncbi_weaver(db_path=mini_db_path)
    assert "local" in weaver._backends


def test_auto_setup_uses_default_path_and_consents(record_ensure, monkeypatch):
    monkeypatch.delenv("BRAIDWORKS_AUTO_DOWNLOAD", raising=False)
    weaver = build_ncbi_weaver(auto_setup=True)
    assert "local" in weaver._backends
    assert record_ensure[0]["target"] == default_db_path()
    assert record_ensure[0]["auto"] is True


def test_interactive_prompt_yes_consents(record_ensure, monkeypatch, tmp_path):
    monkeypatch.delenv("BRAIDWORKS_AUTO_DOWNLOAD", raising=False)
    monkeypatch.setattr(factory, "_interactive", lambda: True)
    monkeypatch.setattr(factory, "_prompt_for_setup", lambda target: True)
    build_ncbi_weaver(db_path=tmp_path / "missing.sqlite")
    assert record_ensure[0]["auto"] is True


def test_interactive_prompt_no_declines(record_ensure, monkeypatch, tmp_path):
    monkeypatch.delenv("BRAIDWORKS_AUTO_DOWNLOAD", raising=False)
    monkeypatch.setattr(factory, "_interactive", lambda: True)
    monkeypatch.setattr(factory, "_prompt_for_setup", lambda target: False)
    build_ncbi_weaver(db_path=tmp_path / "missing.sqlite")
    # Declined -> consent stays False; the real ensure would then raise.
    assert record_ensure[0]["auto"] is False


def test_non_interactive_missing_db_raises_actionable(monkeypatch, tmp_path):
    monkeypatch.delenv("BRAIDWORKS_AUTO_DOWNLOAD", raising=False)
    monkeypatch.setattr(factory, "_interactive", lambda: False)
    with pytest.raises(BackendConfigurationError, match="taxon-weaver ensure"):
        build_ncbi_weaver(db_path=tmp_path / "missing.sqlite")


def test_no_local_no_api_still_requires_a_backend(monkeypatch):
    monkeypatch.setattr(factory, "_interactive", lambda: False)
    with pytest.raises(BackendConfigurationError, match="at least one backend"):
        build_ncbi_weaver()
