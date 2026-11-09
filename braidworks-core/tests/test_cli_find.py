"""`braidworks find WORDS…`: the CLI face of `bw.find`, with the same ranking."""

import csv
import io
import json

import braidworks as bw
import pytest
from braidworks.core import cli
from tests.test_find import _registry


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: _registry())


def _python(text, limit=10):
    with bw.Session(registry=_registry()) as session:
        return session.find(text, limit=limit)


@pytest.mark.parametrize("words", [["pdb", "structures"], ["protein"], ["protein.name"]])
def test_json_matches_python_find(words, capsys):
    assert cli.main(["find", *words, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out) == _python(" ".join(words)).to_json()


def test_quoted_and_split_words_rank_the_same(capsys):
    cli.main(["find", "pdb structures", "--format", "json"])
    quoted = capsys.readouterr().out
    cli.main(["find", "pdb", "structures", "--format", "json"])
    assert capsys.readouterr().out == quoted


def test_human_output_is_the_python_display(capsys):
    assert cli.main(["find", "pdb", "structures"]) == 0
    out = capsys.readouterr().out
    assert out.rstrip("\n") == repr(_python("pdb structures"))
    assert out.startswith("structure.pdb.ids")


def test_limit(capsys):
    assert cli.main(["find", "protein", "--limit", "1", "--format", "json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1


def test_tsv_has_one_row_per_field(capsys):
    assert cli.main(["find", "protein", "--format", "tsv"]) == 0
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out), delimiter="\t"))
    assert [row["type_id"] for row in rows] == [m.type_id for m in _python("protein")]
    assert set(rows[0]) == {"type_id", "description", "sources", "inputs", "score"}


def test_no_match_exits_1_with_a_hint(capsys):
    assert cli.main(["find", "zebrafish"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "braidworks keys" in captured.err


def test_no_match_json_is_an_empty_list(capsys):
    assert cli.main(["find", "zebrafish", "--format", "json"]) == 1
    assert json.loads(capsys.readouterr().out) == []


def test_words_are_required(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["find"])
    assert exc.value.code == 2


def test_limit_must_be_positive(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["find", "protein", "--limit", "0"])
    assert exc.value.code == 2
