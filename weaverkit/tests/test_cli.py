"""CLI tests for ``weaverkit new`` / ``weaverkit verify``.

Drive ``main`` directly with argv and assert exit codes — 0 only when everything
conforms, non-zero on any spec or conformance problem.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from weaverkit.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "valid.weaver.spec.toml"


def test_new_scaffolds_package(tmp_path):
    dest = tmp_path / "madinweaver"
    rc = main(["new", "--spec", str(FIXTURE), "--dest", str(dest)])
    assert rc == 0
    assert (dest / "pyproject.toml").exists()
    assert (dest / "src" / "madinweaver" / "vocab.py").exists()


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
    rc = main(["verify", "--spec", str(FIXTURE), "--package", "madinweaver_absent"])
    assert rc == 0
    assert "not importable" in capsys.readouterr().out


def test_verify_invalid_spec_fails(tmp_path):
    bad = tmp_path / "bad.spec.toml"
    bad.write_text(FIXTURE.read_text().replace('fingerprint_source = "release-tag"', 'fingerprint_source = "unknown"'))
    rc = main(["verify", "--spec", str(bad)])
    assert rc == 1


def test_verify_conforming_generated_package(tmp_path, capsys):
    """new -> import generated package -> verify reports full conformance."""
    dest = tmp_path / "madinweaver"
    assert main(["new", "--spec", str(FIXTURE), "--dest", str(dest)]) == 0

    src = str(dest / "src")
    sys.path.insert(0, src)
    for name in list(sys.modules):
        if name == "madinweaver" or name.startswith("madinweaver."):
            del sys.modules[name]
    try:
        importlib.invalidate_caches()
        rc = main(["verify", "--spec", str(FIXTURE), "--package", "madinweaver"])
    finally:
        sys.path.remove(src)
        for name in list(sys.modules):
            if name == "madinweaver" or name.startswith("madinweaver."):
                del sys.modules[name]
    assert rc == 0
    assert "conforms" in capsys.readouterr().out
