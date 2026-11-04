"""Offline human command journeys through the shared durable service."""

import json

from braidworks.core import cli
from braidworks.core.run_store import SQLiteRunStore
from test_query import _registry
from test_review_continuation import _registry as review_registry


def test_weave_cache_reuse_and_status_resume(monkeypatch, tmp_path, capsys):
    registry = _registry()
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    cache, runs = tmp_path / "cache.sqlite", tmp_path / "runs.sqlite"
    flags = [
        "weave",
        "--have",
        "input.a=value",
        "--want",
        "output.value",
        "--format",
        "json",
        "--cache-db",
        str(cache),
        "--run-db",
        str(runs),
    ]
    assert cli.main(flags + ["--run-id", "one"]) == 0
    initial = capsys.readouterr()
    assert "durable run: one" in initial.err
    calls = registry.get_weaver("a").batch_calls
    assert cli.main(flags + ["--run-id", "two"]) == 0
    capsys.readouterr()
    assert registry.get_weaver("a").batch_calls == calls
    assert cli.main(["runs", "--run-db", str(runs), "--format", "json"]) == 0
    statuses = json.loads(capsys.readouterr().out)
    assert [status["run_id"] for status in statuses] == ["one", "two"]
    assert all(status["status"] == "complete" and "owner" not in status for status in statuses)
    assert cli.main(["resume", "one", "--run-db", str(runs), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(initial.out)
    assert registry.get_weaver("a").batch_calls == calls


def test_cli_review_select_accept_reject_and_duplicate_rows(monkeypatch, tmp_path, capsys):
    registry = review_registry(review_second=True)
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    inputs = tmp_path / "inputs.txt"
    inputs.write_text("x\nx\n")
    runs = tmp_path / "runs.sqlite"
    assert (
        cli.main(
            [
                "weave",
                "--in-file",
                str(inputs),
                "--in-type",
                "input.id",
                "--want",
                "output.id",
                "--run-db",
                str(runs),
                "--run-id",
                "review",
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert len(json.loads(capsys.readouterr().out)) == 2
    assert cli.main(["runs", "review", "--run-db", str(runs), "--format", "json"]) == 0
    status = json.loads(capsys.readouterr().out)
    first, second = [item["strand_set"]["execution_key"] for item in status["reviews"]]
    assert first != second
    assert cli.main(["runs", "review", "--run-db", str(runs)]) == 0
    human = capsys.readouterr().out
    assert "select:0" in human and first in human
    flags = ["resume", "review", "--run-db", str(runs), "--format", "json"]
    assert (
        cli.main(flags + ["--decision", f"{first}=select:0", "--decision", f"{second}=reject"]) == 0
    )
    rows = json.loads(capsys.readouterr().out)
    assert {row["status"] for row in rows} == {"review", "unresolved"}
    assert cli.main(flags + ["--decision", f"{first}=accept"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert {row["status"] for row in rows} == {"resolved", "unresolved"}
    assert SQLiteRunStore(runs).load("review").status == "complete"
    assert registry.get_weaver("first").batch_calls == 1


def test_status_missing_path_never_creates_a_file(tmp_path, capsys):
    path = tmp_path / "missing.sqlite"
    assert cli.main(["runs", "--run-db", str(path)]) == 1
    assert not path.exists()
    assert "could not read" in capsys.readouterr().err


def test_invalid_options_and_existing_id_never_overwrite(monkeypatch, tmp_path, capsys):
    registry = _registry()
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    flags = ["weave", "--have", "input.a=x", "--want", "output.value", "--format", "json"]
    assert cli.main(flags + ["--run-id", "unbound"]) == 1
    assert registry.get_weaver("a").batch_calls == 0
    capsys.readouterr()
    assert (
        cli.main(
            flags + ["--cache-db", str(tmp_path / "cache.sqlite"), "--cache-positive-ttl", "nan"]
        )
        == 1
    )
    assert registry.get_weaver("a").batch_calls == 0
    capsys.readouterr()
    store_path = tmp_path / "runs.sqlite"
    durable = flags + ["--run-db", str(store_path), "--run-id", "saved"]
    assert cli.main(durable) == 0
    capsys.readouterr()
    original = SQLiteRunStore(store_path).load("saved").to_json()
    assert cli.main(durable) == 1
    assert SQLiteRunStore(store_path).load("saved").to_json() == original
    assert "already exists" in capsys.readouterr().err


def test_resume_archive_remains_independent_observation_export(monkeypatch, tmp_path, capsys):
    registry = _registry()
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    path = tmp_path / "runs.sqlite"
    assert (
        cli.main(
            [
                "weave",
                "--have",
                "input.a=x",
                "--want",
                "output.value",
                "--run-db",
                str(path),
                "--run-id",
                "saved",
                "--format",
                "json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    archive = tmp_path / "archive.json"
    assert cli.main(["resume", "saved", "--run-db", str(path), "--archive", str(archive)]) == 0
    payload = json.loads(archive.read_text())
    assert payload["schema"] == "braidworks.run-archive.v1"
    assert payload["records"][0]["values"]["output.value"] == "a"
