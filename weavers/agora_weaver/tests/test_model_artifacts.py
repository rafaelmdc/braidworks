"""Existing model cache files use the same lock/staging safety as other artifacts."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from agora_weaver import setup
from agora_weaver.backends.local import AgoraLocalBackend

MODEL = "Abiotrophia_defectiva_ATCC_49176"
VALID = f'<sbml><model id="{MODEL}"/></sbml>'.encode()


@pytest.mark.parametrize("content", [b"html", b"<html/>", b"<sbml/>", b"<sbml><model id='x'>"])
def test_malformed_download_never_published(tmp_path, monkeypatch, content):
    monkeypatch.setattr(setup, "_download", lambda url, path, **kw: path.write_bytes(content))
    with pytest.raises(setup.InvalidSBML):
        setup.ensure_model_sbml(MODEL, cache_dir=tmp_path, auto=True)
    assert not (tmp_path / f"{MODEL}.xml").exists()


def test_invalid_existing_cache_is_not_returned_or_destroyed_on_failed_download(
    tmp_path, monkeypatch
):
    target = tmp_path / f"{MODEL}.xml"
    target.write_bytes(b"corrupt existing")
    assert setup.ensure_model_sbml(MODEL, cache_dir=tmp_path) is None
    monkeypatch.setattr(setup, "_download", lambda url, path, **kw: path.write_bytes(b"<html/>"))
    with pytest.raises(setup.InvalidSBML):
        setup.ensure_model_sbml(MODEL, cache_dir=tmp_path, auto=True)
    assert target.read_bytes() == b"corrupt existing"


def test_concurrent_model_acquisition_downloads_once(tmp_path, monkeypatch):
    started, release = Event(), Event()
    calls = []

    def download(url, path, **kw):
        calls.append(url)
        started.set()
        assert release.wait(5)
        path.write_bytes(VALID)

    monkeypatch.setattr(setup, "_download", download)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(setup.ensure_model_sbml, MODEL, cache_dir=tmp_path, auto=True)
        assert started.wait(5)
        second = pool.submit(setup.ensure_model_sbml, MODEL, cache_dir=tmp_path, auto=True)
        release.set()
        assert first.result() == second.result()
    assert len(calls) == 1


def test_model_state_and_exported_identity(tmp_path):
    backend = AgoraLocalBackend(sbml_cache_dir=tmp_path)
    before = backend.fingerprint()
    (tmp_path / f"{MODEL}.xml").write_bytes(VALID)
    assert backend.fingerprint() != before
    result = backend._models_for([{"reconstruction_id": MODEL}])[0]
    assert result["sha256"] == hashlib.sha256(VALID).hexdigest()
    assert result["model_id"] == MODEL and result["release"] == "AGORA2-v2.01"
    assert (
        AgoraLocalBackend(sbml_cache_dir=tmp_path / "other").fingerprint() != backend.fingerprint()
    )


def test_model_identifier_cannot_escape_cache_directory(tmp_path):
    with pytest.raises(ValueError, match="safe model identifier"):
        setup.ensure_model_sbml("../escape", cache_dir=tmp_path, auto=True)
