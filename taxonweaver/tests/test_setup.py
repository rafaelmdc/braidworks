"""Unit checks for ensure_taxonomy_db — the local DB auto-setup (no live network)."""

from __future__ import annotations

import hashlib
import io
import tarfile

import pytest

from braidworks.core import BackendConfigurationError
from taxonomy_resolver.service import TaxonomyResolverService
from taxonweaver import setup as setup_mod
from taxonweaver.setup import default_db_path, ensure_taxonomy_db

from tests.test_deterministic_resolution import NAMES_DMP, NODES_DMP, _BytesReader


def _mini_taxdump_bytes() -> bytes:
    """Serialize the synthetic Faecalibacterium taxdump as a .tar.gz byte string."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, content in (("nodes.dmp", NODES_DMP), ("names.dmp", NAMES_DMP)):
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, fileobj=_BytesReader(data))
    return buffer.getvalue()


class _FakeResponse:
    """Minimal urlopen stand-in supporting chunked read + Content-Length header."""

    def __init__(self, payload: bytes, *, content_length: int | None = None) -> None:
        self._payload = payload
        self._offset = 0
        self.headers: dict[str, str] = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size == -1:
            size = len(self._payload) - self._offset
        start = self._offset
        end = min(len(self._payload), self._offset + size)
        self._offset = end
        return self._payload[start:end]


class _FakeNetwork:
    """Dispatch mocked urlopen calls to the taxdump archive or its .md5 sidecar."""

    def __init__(self, tarball: bytes, md5_text: str | None = None) -> None:
        self.tarball = tarball
        self.md5_text = (
            md5_text if md5_text is not None else f"{hashlib.md5(tarball).hexdigest()}  taxdump.tar.gz"
        )
        self.calls: list[str] = []

    def urlopen(self, url: str, *args: object, **kwargs: object) -> _FakeResponse:
        self.calls.append(url)
        if url.endswith(".md5"):
            return _FakeResponse(self.md5_text.encode("utf-8"))
        return _FakeResponse(self.tarball, content_length=len(self.tarball))


@pytest.fixture
def network(monkeypatch) -> _FakeNetwork:
    """Patch setup's urlopen with a deterministic fake serving the mini taxdump."""
    fake = _FakeNetwork(_mini_taxdump_bytes())
    monkeypatch.setattr(setup_mod.urllib.request, "urlopen", fake.urlopen)
    return fake


def test_ensure_builds_db_when_consented(tmp_path, network) -> None:
    db_path = tmp_path / "taxonomy.sqlite"
    result = ensure_taxonomy_db(db_path, auto=True)

    assert result == db_path
    assert setup_mod.db_is_valid(db_path)
    # The built DB is genuinely usable by the resolver service.
    service = TaxonomyResolverService(db_path)
    info = service.get_taxonomy_build_info()
    assert info["taxonomy_build_version"]


def test_ensure_is_idempotent(tmp_path, network) -> None:
    db_path = tmp_path / "taxonomy.sqlite"
    ensure_taxonomy_db(db_path, auto=True)
    download_calls = len([u for u in network.calls if not u.endswith(".md5")])
    assert download_calls == 1

    # A valid DB already present -> no further network access.
    ensure_taxonomy_db(db_path, auto=True)
    assert len([u for u in network.calls if not u.endswith(".md5")]) == 1


def test_ensure_without_consent_raises_actionable(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("BRAIDWORKS_AUTO_DOWNLOAD", raising=False)
    db_path = tmp_path / "taxonomy.sqlite"
    with pytest.raises(BackendConfigurationError) as excinfo:
        ensure_taxonomy_db(db_path, auto=False)
    message = str(excinfo.value)
    assert "taxon-weaver ensure" in message
    assert "auto_setup=True" in message
    assert not db_path.exists()


def test_env_var_grants_consent(tmp_path, network, monkeypatch) -> None:
    monkeypatch.setenv("BRAIDWORKS_AUTO_DOWNLOAD", "1")
    db_path = tmp_path / "taxonomy.sqlite"
    ensure_taxonomy_db(db_path, auto=False)
    assert setup_mod.db_is_valid(db_path)


def test_md5_mismatch_raises_and_leaves_no_db(tmp_path, monkeypatch) -> None:
    fake = _FakeNetwork(_mini_taxdump_bytes(), md5_text="0" * 32 + "  taxdump.tar.gz")
    monkeypatch.setattr(setup_mod.urllib.request, "urlopen", fake.urlopen)
    db_path = tmp_path / "taxonomy.sqlite"
    with pytest.raises(BackendConfigurationError, match="checksum mismatch"):
        ensure_taxonomy_db(db_path, auto=True)
    assert not db_path.exists()


def test_disk_precheck_raises_before_download(tmp_path, network, monkeypatch) -> None:
    monkeypatch.setattr(
        setup_mod, "_MIN_FREE_BYTES", 10**18  # absurdly large requirement
    )
    db_path = tmp_path / "taxonomy.sqlite"
    with pytest.raises(BackendConfigurationError, match="insufficient disk space"):
        ensure_taxonomy_db(db_path, auto=True)
    assert not db_path.exists()


def test_refresh_rebuilds_existing_db(tmp_path, network) -> None:
    db_path = tmp_path / "taxonomy.sqlite"
    ensure_taxonomy_db(db_path, auto=True)
    first_downloads = len([u for u in network.calls if not u.endswith(".md5")])

    ensure_taxonomy_db(db_path, auto=True, refresh=True)
    second_downloads = len([u for u in network.calls if not u.endswith(".md5")])
    assert second_downloads == first_downloads + 1
    assert setup_mod.db_is_valid(db_path)


def test_build_records_source_md5(tmp_path, network) -> None:
    db_path = tmp_path / "taxonomy.sqlite"
    ensure_taxonomy_db(db_path, auto=True)
    assert setup_mod._stored_source_md5(db_path) == hashlib.md5(network.tarball).hexdigest()


def test_check_for_update_current(tmp_path, network) -> None:
    db_path = tmp_path / "taxonomy.sqlite"
    ensure_taxonomy_db(db_path, auto=True)
    # The fake serves the same tarball, so the remote md5 matches the stored one.
    assert setup_mod.check_for_update(db_path) is False


def test_check_for_update_newer_available(tmp_path, network, monkeypatch) -> None:
    db_path = tmp_path / "taxonomy.sqlite"
    ensure_taxonomy_db(db_path, auto=True)
    monkeypatch.setattr(setup_mod, "_fetch_remote_md5", lambda url: "f" * 32)
    assert setup_mod.check_for_update(db_path) is True


def test_check_for_update_undetermined(tmp_path, network, monkeypatch) -> None:
    db_path = tmp_path / "taxonomy.sqlite"
    ensure_taxonomy_db(db_path, auto=True)
    monkeypatch.setattr(setup_mod, "_fetch_remote_md5", lambda url: None)
    assert setup_mod.check_for_update(db_path) is None


def test_default_db_path_respects_data_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BRAIDWORKS_DATA_DIR", str(tmp_path))
    assert default_db_path() == tmp_path / "taxonomy" / "taxonomy.sqlite"


def test_default_db_path_uses_cache_dir(monkeypatch) -> None:
    monkeypatch.delenv("BRAIDWORKS_DATA_DIR", raising=False)
    path = default_db_path()
    assert path.name == "taxonomy.sqlite"
    assert "braidworks" in str(path)
