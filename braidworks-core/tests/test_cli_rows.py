"""The CLI prints Python's `Result` rows: labelled by input, with status and list totals."""

import json

import braidworks as bw
import pytest
from braidworks.core import cli
from braidworks.core.listing import Listing
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import WeaveResult, WeaveStatus
from braidworks.core.strand import Strand
from tests.helpers import ScriptedWeaver, simple_capability
from tests.test_cli import _make_registry

WANT = ["protein.name", "structure.pdb.ids"]
CAP = simple_capability("resolve_protein", {"protein.query"}, set(WANT))


def _resolve(ss, backend, requested):
    query = ss.get("protein.query").value
    if query == "MISS":
        return WeaveResult(CAP.id, "1.0.0", backend, frozenset({"g"}), WeaveStatus.NO_MATCH)
    ids = Listing(["1abc", "2def"], total=5) if query == "PART" else ["1abc", "2def"]
    strands = [Strand("structure.pdb.ids", ids)]
    if query != "NONAME":
        strands.append(Strand("protein.name", f"Name of {query}"))
    return WeaveResult(
        CAP.id, "1.0.0", backend, frozenset({"g"}), WeaveStatus.OK, strands=tuple(strands)
    )


def _registry() -> BraidRegistry:
    registry = BraidRegistry()
    registry.register(ScriptedWeaver(_resolve, capability=CAP, weaver_id="uniprot"))
    return registry


@pytest.fixture(autouse=True)
def _patch_discovery(monkeypatch):
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: _registry())


IDS = ["P1", "PART", "MISS", "NONAME", "P1"]


def _cli(capsys, *extra):
    argv = ["get", *IDS, "--have", "protein.query", "--want", ",".join(WANT), *extra]
    code = cli.main(argv)
    return code, capsys.readouterr()


def _python():
    with bw.Session(registry=_registry()) as session:
        return session.get(IDS, have="protein.query", want=WANT)


@pytest.mark.parametrize(("fmt", "sep"), [("csv", ","), ("tsv", "\t")])
def test_csv_and_tsv_are_python_to_csv(fmt, sep, capsys):
    code, captured = _cli(capsys, "--format", fmt)
    assert code == 0
    assert captured.out == _python().to_csv(sep=sep)
    assert captured.out.splitlines()[0].split(sep) == [
        "input",
        "row",
        "status",
        "protein.name",
        "structure.pdb.ids",
        "structure.pdb.ids.total",
        "missing",
    ]


def test_json_is_python_to_json(capsys):
    _, captured = _cli(capsys, "--format", "json")
    assert json.loads(captured.out) == json.loads(json.dumps(_python().to_json()))


def test_jsonl_is_one_python_row_per_line(capsys):
    _, captured = _cli(capsys, "--format", "jsonl")
    lines = [json.loads(line) for line in captured.out.splitlines()]
    assert lines == json.loads(json.dumps(_python().rows))
    assert [line["input"] for line in lines] == IDS


def test_human_rows_are_labelled_by_input_with_status_and_totals(capsys):
    _, captured = _cli(capsys)
    blocks = captured.out.strip().split("\n\n")
    assert blocks == [
        "P1  (row 1)  [resolved]\n  protein.name: Name of P1\n  structure.pdb.ids (2): 1abc; 2def",
        "PART  [resolved]\n  protein.name: Name of PART\n  structure.pdb.ids (2 of 5): 1abc; 2def",
        "MISS  [unresolved]\n  missing: protein.name, structure.pdb.ids",
        "NONAME  [resolved]\n  structure.pdb.ids (2): 1abc; 2def\n  missing: protein.name",
        "P1  (row 5)  [resolved]\n  protein.name: Name of P1\n  structure.pdb.ids (2): 1abc; 2def",
    ]


def test_summary_line_is_pythons_on_stderr(capsys):
    _, captured = _cli(capsys)
    assert f"→ {_python().summary()}" in captured.err
    assert "5 inputs · 4 resolved · 1 unresolved · 0 need review · 0 errors" in captured.err


def test_run_prints_the_same_row_schema(capsys):
    argv = ["run", "uniprot", CAP.id, "--have", "protein.query=PART", "--format", "json"]
    assert cli.main(argv) == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert list(data) == ["summary", "want", "rows", "references", "result"]
    assert data["want"] == sorted(WANT)
    assert data["rows"] == [
        {
            "input": "e1",
            "row": 1,
            "status": "resolved",
            "protein.name": "Name of PART",
            "structure.pdb.ids": ["1abc", "2def"],
            "missing": [],
        }
    ]
    assert data["result"]["direct_results"][0]["capability_id"] == CAP.id
    assert "→ 1 input · 1 resolved" in captured.err


def test_run_human_shows_list_totals(capsys):
    assert cli.main(["run", "uniprot", CAP.id, "--have", "protein.query=PART"]) == 0
    assert "structure.pdb.ids (2 of 5): 1abc; 2def" in capsys.readouterr().out


def test_python_for_each_without_want_shows_the_fanned_key():
    with bw.Session(registry=_make_registry()) as session:
        result = session.get("ACC_X", have="protein.uniprot.accession", for_each="structures")
    assert result.want == ["pdb.id"]
    assert sorted(row["pdb.id"] for row in result.rows) == ["ACC_X-1", "ACC_X-2"]
