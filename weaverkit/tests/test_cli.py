"""CLI tests for ``weaverkit new`` / ``weaverkit verify``.

Drive ``main`` directly with argv and assert exit codes — 0 only when everything
conforms, non-zero on any spec or conformance problem.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from weaverkit.cli import (
    _build_fixture_weaver,
    _first_runnable_backend,
    _provenance_warnings,
    _version_drift_warning,
    main,
)
from weaverkit.spec import load_spec

FIXTURE = Path(__file__).parent / "fixtures" / "valid.weaver.spec.toml"


def _spec(**overrides):
    spec = load_spec(FIXTURE)
    return spec.__class__(**{**spec.__dict__, **overrides})


def test_provenance_warning_unknown_license():
    warnings = _provenance_warnings(_spec(license="Proprietary-EULA"))
    assert any("not a known identifier" in w for w in warnings)


def test_provenance_warning_attribution_license_missing_citation():
    warnings = _provenance_warnings(_spec(license="CC-BY-4.0", citation=""))
    assert any("requires attribution" in w for w in warnings)


def test_provenance_no_warning_when_complete():
    spec = _spec(license="CC-BY-4.0", citation="https://doi.org/10.1093/nar/xyz")
    assert _provenance_warnings(spec) == []
    assert _provenance_warnings(_spec(license="CC0-1.0", citation="")) == []


def _write_pyproject(tmp_path, version):
    spec_path = tmp_path / "weaver.spec.toml"
    spec_path.write_text(FIXTURE.read_text())
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "madin_weaver"\nversion = "{version}"\n'
    )
    return spec_path


def test_version_drift_warns(tmp_path):
    spec_path = _write_pyproject(tmp_path, "0.9.9")  # fixture spec version is 0.1.0
    warnings = _version_drift_warning(load_spec(spec_path), str(spec_path))
    assert any("version drift" in w for w in warnings)


def test_version_no_drift_when_aligned(tmp_path):
    spec_path = _write_pyproject(tmp_path, "0.1.0")
    assert _version_drift_warning(load_spec(spec_path), str(spec_path)) == []


def test_version_drift_skips_when_no_pyproject(tmp_path):
    spec_path = tmp_path / "weaver.spec.toml"
    spec_path.write_text(FIXTURE.read_text())
    assert _version_drift_warning(load_spec(spec_path), str(spec_path)) == []


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


# --- references command -------------------------------------------------------

import json as _json  # noqa: E402

import weaverkit.view as view_mod  # noqa: E402
from braidworks.core import (  # noqa: E402
    Capability,
    OutputGroup,
    Provenance,
    WeaverManifest,
)
from braidworks.core.registry import BraidRegistry  # noqa: E402
from braidworks.core.weaver import BaseWeaver  # noqa: E402
from weaverkit.view import Discovery  # noqa: E402


class _ProvWeaver(BaseWeaver):
    def __init__(self, manifest):
        self._m = manifest

    @property
    def MANIFEST(self):  # type: ignore[override]
        return self._m

    def backend_fingerprint(self, backend):
        return "fp"

    async def execute(self, *a, **k):  # pragma: no cover - never executed here
        raise NotImplementedError


def _refs_registry():
    reg = BraidRegistry()
    reg.register(
        _ProvWeaver(
            WeaverManifest(
                weaver_id="uniprot",
                version="0.1.1",
                capabilities=(
                    Capability(
                        id="c",
                        consumes=frozenset({"protein.query"}),
                        produces=frozenset({"protein.uniprot.accession"}),
                        output_groups=(OutputGroup(id="g", outputs=frozenset({"protein.uniprot.accession"})),),
                        backends=("api",),
                    ),
                ),
                provenance=Provenance(
                    source_url="https://www.uniprot.org",
                    license="CC-BY-4.0",
                    citation="https://doi.org/x",
                    attribution="UniProt Consortium",
                ),
            )
        )
    )
    reg.register(
        _ProvWeaver(
            WeaverManifest(
                weaver_id="bare",
                version="1.0.0",
                capabilities=(
                    Capability(
                        id="c",
                        consumes=frozenset({"a"}),
                        produces=frozenset({"b"}),
                        output_groups=(OutputGroup(id="g", outputs=frozenset({"b"})),),
                        backends=("api",),
                    ),
                ),
            )
        )
    )
    return reg


def _patch_discovery(monkeypatch):
    monkeypatch.setattr(
        view_mod, "discover_registry", lambda: Discovery(registry=_refs_registry(), problems=[])
    )


def test_references_all(monkeypatch, capsys):
    _patch_discovery(monkeypatch)
    assert main(["references"]) == 0
    out = capsys.readouterr().out
    assert "UniProt Consortium" in out
    assert "attribution required" in out


def test_references_weaver_filter(monkeypatch, capsys):
    _patch_discovery(monkeypatch)
    assert main(["references", "--weaver", "bare"]) == 0
    out = capsys.readouterr().out
    assert "no references" in out  # bare has no provenance


def test_references_json(monkeypatch, capsys):
    _patch_discovery(monkeypatch)
    assert main(["references", "--weaver", "uniprot", "--json"]) == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload[0]["weaver_id"] == "uniprot"
    assert payload[0]["requirement"] == "attribution_required"


def test_references_from_without_to_errors(monkeypatch, capsys):
    _patch_discovery(monkeypatch)
    assert main(["references", "--from", "protein.query"]) == 1
    assert "must be given together" in capsys.readouterr().err
