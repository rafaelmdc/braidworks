"""`braidworks get ID… --have TYPE --want …`: positional IDs; `weave` is an alias."""

import json

import pytest
from braidworks.core import cli
from test_query import _registry


@pytest.fixture
def registry(monkeypatch):
    reg = _registry()
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: reg)
    return reg


def _json(capsys):
    return json.loads(capsys.readouterr().out)["rows"]


def test_positional_ids_are_typed_by_bare_have(registry, capsys):
    argv = ["get", "P1", "P2", "--have", "input.a", "--want", "output.value", "--format", "json"]
    assert cli.main(argv) == 0
    records = _json(capsys)
    assert [r["input"] for r in records] == ["P1", "P2"]
    assert [r["row"] for r in records] == [1, 2]
    assert all(r["output.value"] == "a" and r["status"] == "resolved" for r in records)


def test_ids_may_follow_options(registry, capsys):
    argv = ["get", "P1", "--have", "input.a", "--want", "output.value", "P2", "--format", "json"]
    assert cli.main(argv) == 0
    assert [r["input"] for r in _json(capsys)] == ["P1", "P2"]


def test_duplicate_ids_stay_distinct_rows(registry, capsys):
    argv = ["get", "P1", "P1", "--have", "input.a", "--want", "output.value", "--format", "json"]
    assert cli.main(argv) == 0
    assert [r["row"] for r in _json(capsys)] == [1, 2]


def test_constants_broadcast_onto_every_id():
    args = cli.build_parser().parse_args(
        ["get", "P1", "P2", "--have", "input.a", "--have", "extra.tag=x", "--want", "y"]
    )
    sets = cli._collect_inputs(args)
    assert [ss.entity_id for ss in sets] == ["P1", "P2"]
    assert [ss.get("input.a").value for ss in sets] == ["P1", "P2"]
    assert [ss.get("extra.tag").value for ss in sets] == ["x", "x"]


@pytest.mark.parametrize("verb", ["get", "weave"])
def test_type_value_form_still_works_under_both_verbs(verb, registry, capsys):
    argv = [verb, "--have", "input.a=value", "--want", "output.value", "--format", "json"]
    assert cli.main(argv) == 0
    assert [r["input"] for r in _json(capsys)] == ["e1"]


def test_weave_alias_accepts_positional_ids(registry, capsys):
    argv = ["weave", "P1", "--have", "input.a", "--want", "output.value", "--format", "json"]
    assert cli.main(argv) == 0
    assert [r["input"] for r in _json(capsys)] == ["P1"]


def test_in_file_still_works_under_get(registry, tmp_path, capsys):
    path = tmp_path / "ids.txt"
    path.write_text("P1\nP2\n")
    argv = ["get", "--in-file", str(path), "--in-type", "input.a", "--want", "output.value"]
    assert cli.main(argv + ["--format", "json"]) == 0
    assert [r["input"] for r in _json(capsys)] == ["P1", "P2"]


def test_get_saves_a_run_like_weave(registry, tmp_path, capsys):
    runs = tmp_path / "runs.sqlite"
    argv = ["get", "P1", "--have", "input.a", "--want", "output.value"]
    assert cli.main(argv + ["--run-db", str(runs), "--run-id", "one"]) == 0
    assert "durable run: one" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["get", "P1", "--want", "output.value"], "--have TYPE"),
        (["get", "--have", "input.a", "--want", "output.value"], "no IDs"),
        (["get", "P1", "--have", "input.a", "--have", "input.b", "--want", "x"], "one type"),
        (["get", "P1", "--have", "input.a", "--in-file", "f.txt", "--want", "x"], "not both"),
    ],
)
def test_input_mistakes_explain_themselves(argv, message, registry):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert message in str(exc.value)


def test_unknown_option_is_still_rejected(registry, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["get", "P1", "--have", "input.a", "--want", "output.value", "--bogus"])
    assert exc.value.code == 2
    assert "unrecognized arguments: --bogus" in capsys.readouterr().err


def test_other_commands_reject_stray_arguments(registry, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["keys", "stray"])
    assert exc.value.code == 2
