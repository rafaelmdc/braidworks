"""CLI tests for ``weaverkit new`` / ``weaverkit verify``.

Drive ``main`` directly with argv and assert exit codes — 0 only when everything
conforms, non-zero on any spec or conformance problem.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from weaverkit.cli import _build_fixture_weaver, _first_runnable_backend, main

FIXTURE = Path(__file__).parent / "fixtures" / "valid.weaver.spec.toml"


class _FakeWeaver:
    """Minimal stand-in exposing only backend_fingerprint, for helper unit tests."""

    def __init__(self, fps: dict[str, object]) -> None:
        self._fps = fps

    def backend_fingerprint(self, backend: str) -> str:
        v = self._fps[backend]
        if isinstance(v, Exception):
            raise v
        return str(v)


def test_first_runnable_backend_picks_first_configured():
    w = _FakeWeaver({"local": "unconfigured:local", "api": "datasets-v2"})
    assert _first_runnable_backend(w, ("local", "api")) == "api"


def test_first_runnable_backend_none_when_all_unconfigured():
    w = _FakeWeaver({"local": "unconfigured:local", "api": "unknown"})
    assert _first_runnable_backend(w, ("local", "api")) is None


def test_first_runnable_backend_skips_raising_backend():
    w = _FakeWeaver({"local": RuntimeError("boom"), "api": "real-v1"})
    assert _first_runnable_backend(w, ("local", "api")) == "api"


def test_build_fixture_weaver_absent_returns_none(tmp_path):
    pkg = tmp_path / "src" / "nofixture_weaver"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "factory.py").write_text("def build_nofixture_weaver(**c):\n    return None\n")
    src = str(tmp_path / "src")
    sys.path.insert(0, src)
    try:
        importlib.invalidate_caches()
        assert _build_fixture_weaver("nofixture_weaver") is None
    finally:
        sys.path.remove(src)
        for name in list(sys.modules):
            if name == "nofixture_weaver" or name.startswith("nofixture_weaver."):
                del sys.modules[name]


def test_new_scaffolds_package(tmp_path):
    dest = tmp_path / "madin_weaver"
    rc = main(["new", "--spec", str(FIXTURE), "--dest", str(dest)])
    assert rc == 0
    assert (dest / "pyproject.toml").exists()
    assert (dest / "src" / "madin_weaver" / "vocab.py").exists()


def test_new_rejects_invalid_spec(tmp_path, capsys):
    bad = tmp_path / "bad.spec.toml"
    bad.write_text(FIXTURE.read_text().replace('"ncbi.taxon.id"', '"not.a.key"'))
    rc = main(["new", "--spec", str(bad), "--dest", str(tmp_path / "out")])
    assert rc == 1
    assert "invalid" in capsys.readouterr().err


def test_new_refuses_nonempty_dest(tmp_path):
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "x").write_text("x")
    rc = main(["new", "--spec", str(FIXTURE), "--dest", str(dest)])
    assert rc == 1


def test_verify_valid_spec_uninstalled_package_is_ok(tmp_path, capsys):
    """verify on a valid spec whose package isn't importable: spec-only pass (rc 0)."""
    rc = main(["verify", "--spec", str(FIXTURE), "--package", "madin_weaver_absent"])
    assert rc == 0
    assert "not importable" in capsys.readouterr().out


def test_verify_invalid_spec_fails(tmp_path):
    bad = tmp_path / "bad.spec.toml"
    bad.write_text(
        FIXTURE.read_text().replace(
            'fingerprint_source = "release-tag"', 'fingerprint_source = "unknown"'
        )
    )
    rc = main(["verify", "--spec", str(bad)])
    assert rc == 1


def _with_generated_on_path(dest, package):
    """Context-free helper: put a generated package's src on sys.path, cleaned up."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        src = str(dest / "src")
        sys.path.insert(0, src)
        for name in list(sys.modules):
            if name == package or name.startswith(package + "."):
                del sys.modules[name]
        importlib.invalidate_caches()
        try:
            yield
        finally:
            sys.path.remove(src)
            for name in list(sys.modules):
                if name == package or name.startswith(package + "."):
                    del sys.modules[name]

    return _ctx()


def test_verify_strict_fails_on_fresh_scaffold(tmp_path, capsys):
    """A fresh scaffold conforms but is NOT done — --strict must reject it."""
    dest = tmp_path / "madin_weaver"
    assert main(["new", "--spec", str(FIXTURE), "--dest", str(dest)]) == 0
    with _with_generated_on_path(dest, "madin_weaver"):
        # non-strict passes (structure is right)...
        assert main(["verify", "--spec", str(FIXTURE), "--package", "madin_weaver"]) == 0
        # ...strict fails (placeholders remain).
        rc = main(["verify", "--spec", str(FIXTURE), "--package", "madin_weaver", "--strict"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "not done" in err
    assert "placeholder" in err


def test_verify_strict_reports_missing_package(tmp_path, capsys):
    rc = main(["verify", "--spec", str(FIXTURE), "--package", "nope_absent", "--strict"])
    assert rc == 1
    assert "not importable" in capsys.readouterr().err


def test_verify_reports_misnamed_builder_without_crashing(tmp_path, capsys):
    """A package whose factory imports but lacks build_<package> gets a clean finding.

    This is taxon_weaver's real case: the factory module is importable, but its
    builder is named differently (build_ncbi_weaver), so verify must report a fix
    instead of crashing with an AttributeError traceback.
    """
    pkg = tmp_path / "src" / "madin_weaver"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    # Factory imports fine, but the builder is named differently (build_ncbi_weaver,
    # not the expected build_madin_weaver) — taxon_weaver's real case.
    (pkg / "factory.py").write_text("def build_ncbi_weaver(**c):\n    raise SystemExit\n")
    src = str(tmp_path / "src")
    sys.path.insert(0, src)
    try:
        importlib.invalidate_caches()
        rc = main(["verify", "--spec", str(FIXTURE), "--package", "madin_weaver"])
    finally:
        sys.path.remove(src)
        for name in list(sys.modules):
            if name == "madin_weaver" or name.startswith("madin_weaver."):
                del sys.modules[name]
    assert rc == 1
    err = capsys.readouterr().err
    assert "has no build_madin_weaver" in err
    assert "Traceback" not in err


def test_verify_conforming_generated_package(tmp_path, capsys):
    """new -> import generated package -> verify reports full conformance."""
    dest = tmp_path / "madin_weaver"
    assert main(["new", "--spec", str(FIXTURE), "--dest", str(dest)]) == 0

    src = str(dest / "src")
    sys.path.insert(0, src)
    for name in list(sys.modules):
        if name == "madin_weaver" or name.startswith("madin_weaver."):
            del sys.modules[name]
    try:
        importlib.invalidate_caches()
        rc = main(["verify", "--spec", str(FIXTURE), "--package", "madin_weaver"])
    finally:
        sys.path.remove(src)
        for name in list(sys.modules):
            if name == "madin_weaver" or name.startswith("madin_weaver."):
                del sys.modules[name]
    assert rc == 0
    assert "conforms" in capsys.readouterr().out
