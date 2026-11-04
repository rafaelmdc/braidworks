"""Tests for braidworks.core.localdb — the generic local-DB acquisition plumbing.

No network: the build callback writes a local file, so the orchestration (validity
short-circuit, consent gate, atomic publish, refresh, lock) is exercised directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

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
    # Keep a stable inode: removing the file would split contending owners.
    assert (tmp_path / "db.sqlite.lock").exists()
    with BuildLock(db, timeout=0):
        pass


def test_download_sends_braidworks_user_agent(monkeypatch, tmp_path):
    """download() must set a User-Agent, else CDN bot-filters (VMH/Cloudflare) 403 it."""
    import urllib.request

    from braidworks.core.localdb import USER_AGENT, download

    captured: dict[str, object] = {}

    class _FakeResponse:
        headers: ClassVar[dict[str, str]] = {"Content-Length": "3"}

        def __init__(self) -> None:
            self._chunks = [b"abc", b""]

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self, _n):
            return self._chunks.pop(0)

    def _fake_urlopen(request, *, timeout):
        captured["ua"] = request.get_header("User-agent")
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    destination = tmp_path / "f.bin"
    download("https://example.test/f.bin", destination)

    assert captured["timeout"] == 30.0
    assert captured["ua"] == USER_AGENT
    assert destination.read_bytes() == b"abc"


def test_download_reports_before_network_and_preserves_timeout(monkeypatch, tmp_path, capsys):
    from braidworks.core.localdb import download

    events = []

    def stalled(request, *, timeout):
        assert events == [("download", "Downloading", 0, None, False)]
        assert timeout == 2
        raise TimeoutError("signed URL must not be printed")

    monkeypatch.setattr("urllib.request.urlopen", stalled)
    with pytest.raises(TimeoutError):
        download(
            "https://example.test/?secret=token",
            tmp_path / "file",
            progress=lambda *e: events.append(e),
            timeout=2,
        )
    assert events[-1] == ("failed", "Downloading", 0, None, True)
    assert capsys.readouterr().err == ""


def test_default_progress_reports_stall_without_exposing_url(monkeypatch, tmp_path, capsys):
    from braidworks.core.localdb import download

    def stalled(request, **kwargs):
        assert "in progress" in capsys.readouterr().err
        raise TimeoutError("secret")

    monkeypatch.setattr("urllib.request.urlopen", stalled)
    with pytest.raises(TimeoutError):
        download("https://example.test/?secret=token", tmp_path / "file")
    stderr = capsys.readouterr().err
    assert "failed" in stderr
    assert "secret" not in stderr


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_download_timeout_has_no_side_effects(tmp_path, timeout):
    from braidworks.core.localdb import download

    target = tmp_path / "absent" / "file"
    with pytest.raises(ValueError):
        download("https://example.test/", target, timeout=timeout)
    assert not target.parent.exists()


def test_progress_throttles_unknown_length(monkeypatch, capsys):
    from braidworks.core.localdb import _stderr_progress

    moments = iter([0, 1, 11, 12])
    monkeypatch.setattr("braidworks.core.localdb.time.monotonic", lambda: next(moments))
    report = _stderr_progress()
    report("download", "data", 0, None, False)
    report("download", "data", 10, None, False)
    report("download", "data", 20, None, False)
    report("download", "data", 30, None, True)
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 3
    assert "(20 bytes)" in lines[1] and "[done]" in lines[-1]


def test_build_failure_reports_and_keeps_old_artifact(tmp_path):
    target = tmp_path / "data.sqlite"
    target.write_text("old")
    events = []

    def fail(path):
        path.write_text("partial")
        raise RuntimeError("bad build")

    with pytest.raises(RuntimeError):
        ensure_local_db(
            target,
            is_valid=lambda p: p.exists(),
            build=fail,
            consent_message="consent",
            auto=True,
            refresh=True,
            min_free_bytes=0,
            progress=lambda *e: events.append(e),
        )
    assert target.read_text() == "old"
    assert events[-1][0] == "failed"


def test_valid_artifact_stays_silent(tmp_path, capsys):
    target = tmp_path / "data.sqlite"
    target.write_text("valid")
    ensure_local_db(
        target,
        is_valid=lambda p: p.exists(),
        build=lambda p: pytest.fail("must not build"),
        consent_message="consent",
    )
    assert capsys.readouterr().err == ""


def test_checksum_request_is_bounded_and_redacts_failure(monkeypatch, caplog):
    from braidworks.core.localdb import fetch_remote_md5

    def stalled(url, *, timeout):
        assert timeout == 30
        raise TimeoutError("secret=token")

    monkeypatch.setattr("urllib.request.urlopen", stalled)
    assert fetch_remote_md5("https://example.test/?secret=token") is None
    assert "TimeoutError" in caplog.text
    assert "secret" not in caplog.text
