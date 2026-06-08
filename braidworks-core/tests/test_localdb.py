"""Tests for braidworks.core.localdb — the generic local-DB acquisition plumbing.

No network: the build callback writes a local file, so the orchestration (validity
short-circuit, consent gate, atomic publish, refresh, lock) is exercised directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from braidworks.core import BackendConfigurationError
from braidworks.core.localdb import (
    BuildLock,
    auto_consented,
    check_disk,
    default_db_path,
    ensure_local_db,
    md5_file,
)


def _valid(p: Path) -> bool:
    return p.exists() and p.read_text() == "ok"


def test_default_db_path_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAIDWORKS_DATA_DIR", str(tmp_path))
    assert default_db_path("taxonomy", "db.sqlite") == tmp_path / "taxonomy" / "db.sqlite"


def test_default_db_path_uses_cache_dir(monkeypatch):
    monkeypatch.delenv("BRAIDWORKS_DATA_DIR", raising=False)
    p = default_db_path("ns", "db.sqlite")
    assert p.name == "db.sqlite" and "braidworks" in str(p)


def test_auto_consented(monkeypatch):
    monkeypatch.delenv("BRAIDWORKS_AUTO_DOWNLOAD", raising=False)
    assert auto_consented(True) is True
    assert auto_consented(False) is False
    monkeypatch.setenv("BRAIDWORKS_AUTO_DOWNLOAD", "yes")
    assert auto_consented(False) is True


def test_md5_file(tmp_path):
    f = tmp_path / "x"
    f.write_bytes(b"abc")
    assert md5_file(f) == "900150983cd24fb0d6963f7d28e17f72"


def test_check_disk_raises_when_insufficient(tmp_path):
    with pytest.raises(BackendConfigurationError, match="insufficient disk space"):
        check_disk(tmp_path, min_free_bytes=10**18)


def test_ensure_builds_and_publishes(tmp_path):
    db = tmp_path / "db.sqlite"
    calls = {"n": 0}

    def build(target: Path) -> None:
        calls["n"] += 1
        target.write_text("ok")

    result = ensure_local_db(db, is_valid=_valid, build=build, consent_message="no", auto=True)
    assert result == db and _valid(db) and calls["n"] == 1


def test_ensure_is_idempotent(tmp_path):
    db = tmp_path / "db.sqlite"
    calls = {"n": 0}

    def build(target: Path) -> None:
        calls["n"] += 1
        target.write_text("ok")

    ensure_local_db(db, is_valid=_valid, build=build, consent_message="no", auto=True)
    ensure_local_db(db, is_valid=_valid, build=build, consent_message="no", auto=True)
    assert calls["n"] == 1  # second call short-circuits on the valid DB


def test_ensure_without_consent_raises_and_publishes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAIDWORKS_AUTO_DOWNLOAD", raising=False)
    db = tmp_path / "db.sqlite"

    def build(target: Path) -> None:  # pragma: no cover - must not run
        target.write_text("ok")

    with pytest.raises(BackendConfigurationError, match="build it please"):
        ensure_local_db(
            db, is_valid=_valid, build=build, consent_message="build it please", auto=False
        )
    assert not db.exists()


def test_ensure_refresh_rebuilds(tmp_path):
    db = tmp_path / "db.sqlite"
    calls = {"n": 0}

    def build(target: Path) -> None:
        calls["n"] += 1
        target.write_text("ok")

    ensure_local_db(db, is_valid=_valid, build=build, consent_message="no", auto=True)
    ensure_local_db(db, is_valid=_valid, build=build, consent_message="no", auto=True, refresh=True)
    assert calls["n"] == 2


def test_ensure_build_failure_leaves_no_db(tmp_path):
    db = tmp_path / "db.sqlite"

    def build(target: Path) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        ensure_local_db(db, is_valid=_valid, build=build, consent_message="no", auto=True)
    assert not db.exists()


def test_ensure_invalid_build_not_published(tmp_path):
    db = tmp_path / "db.sqlite"

    def build(target: Path) -> None:
        target.write_text("garbage")  # _valid() will reject it

    with pytest.raises(BackendConfigurationError, match="failed validation"):
        ensure_local_db(db, is_valid=_valid, build=build, consent_message="no", auto=True)
    assert not db.exists()


def test_build_lock_acquires_and_releases(tmp_path):
    db = tmp_path / "db.sqlite"
    lock = BuildLock(db)
    with lock:
        assert (tmp_path / "db.sqlite.lock").exists()
    assert not (tmp_path / "db.sqlite.lock").exists()
