"""CLI `ensure` subcommand: consent gate, idempotency, and progress wiring."""

from __future__ import annotations

import argparse

import pytest

from taxonomy_tools import ensure as ensure_cmd
from taxonomy_tools.cli import build_parser


def _args(**overrides) -> argparse.Namespace:
    base = {"db": None, "refresh": False, "yes": False, "url": "https://example.invalid/x.tar.gz"}
    base.update(overrides)
    return argparse.Namespace(func=ensure_cmd.run, **base)


def test_ensure_subcommand_is_registered() -> None:
    parser = build_parser()
    args = parser.parse_args(["ensure", "--yes", "--db", "/tmp/x.sqlite"])
    assert args.func is ensure_cmd.run
    assert args.yes is True


def test_already_present_skips_setup(tmp_path, mini_db_path, monkeypatch, capsys) -> None:
    def _boom(*_a, **_k):
        raise AssertionError("ensure_taxonomy_db must not run when DB is valid")

    monkeypatch.setattr(ensure_cmd, "ensure_taxonomy_db", _boom)
    ensure_cmd.run(_args(db=str(mini_db_path)))
    assert "already present" in capsys.readouterr().out


def test_yes_flag_consents_and_builds(tmp_path, monkeypatch, capsys) -> None:
    calls: list[dict] = []

    def _fake(target, *, auto, refresh=False, url=None, progress=None):
        calls.append({"auto": auto, "refresh": refresh})
        return target

    monkeypatch.setattr(ensure_cmd, "ensure_taxonomy_db", _fake)
    target = tmp_path / "taxonomy.sqlite"
    ensure_cmd.run(_args(db=str(target), yes=True))
    assert calls == [{"auto": True, "refresh": False}]
    assert "Taxonomy DB ready" in capsys.readouterr().out


def test_non_interactive_without_yes_aborts(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("BRAIDWORKS_AUTO_DOWNLOAD", raising=False)
    monkeypatch.setattr(ensure_cmd.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(ensure_cmd.sys.stdout, "isatty", lambda: False)

    def _boom(*_a, **_k):
        raise AssertionError("must not build without consent")

    monkeypatch.setattr(ensure_cmd, "ensure_taxonomy_db", _boom)
    with pytest.raises(SystemExit) as excinfo:
        ensure_cmd.run(_args(db=str(tmp_path / "taxonomy.sqlite")))
    assert excinfo.value.code == 1


def test_env_var_consents_without_yes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BRAIDWORKS_AUTO_DOWNLOAD", "1")
    monkeypatch.setattr(ensure_cmd.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(ensure_cmd.sys.stdout, "isatty", lambda: False)
    calls: list[bool] = []
    monkeypatch.setattr(
        ensure_cmd,
        "ensure_taxonomy_db",
        lambda target, *, auto, refresh=False, url=None, progress=None: calls.append(auto) or target,
    )
    ensure_cmd.run(_args(db=str(tmp_path / "taxonomy.sqlite")))
    assert calls == [True]
