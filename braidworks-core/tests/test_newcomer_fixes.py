"""Fixes from the newcomer walkthrough (5.2): clear errors and unsurprising output."""

from __future__ import annotations

import pytest
from braidworks.core import cli
from braidworks.core.inputs import row_label
from tests.test_api import session  # noqa: F401  (fixture)
from tests.test_cli import _doctor_report, _run


def test_a_missing_input_file_is_a_one_line_error(tmp_path):
    missing = tmp_path / "genes.txt"
    with pytest.raises(SystemExit, match=r"cannot read --in-file .*genes\.txt: No such file"):
        _run("get", "--in-file", str(missing), "--in-type", "protein.query", "--want", "x")


def test_table_rows_are_labelled_by_their_values():
    assert row_label({"protein.query": "TP53"}) == "TP53"
    assert row_label({"protein.query": "TP53", "ncbi.taxon.id": "9606"}) == (
        "protein.query=TP53; ncbi.taxon.id=9606"
    )


def test_to_csv_with_a_path_writes_and_returns_nothing(session, tmp_path):  # noqa: F811
    result = session.get(["P1"], have="protein.query", want="protein.name")
    path = tmp_path / "out.csv"
    assert result.to_csv(path) is None
    assert path.read_text() == result.to_csv()


def test_repr_marks_shortened_values(session):  # noqa: F811
    result = session.get(["P1"], have="protein.query", want="structure.pdb.ids")
    long_row = result.rows[0]
    long_row["structure.pdb.ids"] = ["X" * 30, "Y" * 30]
    assert "…" in repr(result)


def test_doctor_points_to_the_setup_guide_when_a_source_needs_it(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "discover_registry", _doctor_report())
    monkeypatch.setattr(
        cli,
        "backend_readiness",
        lambda registry, wid: ([], ["local"]) if wid == "pdbe" else (["api"], []),
    )
    _run("doctor")
    out = capsys.readouterr().out
    assert "○ pdbe" in out and "needs setup: local" in out
    assert "To set up local data: " + cli.SETUP_GUIDE in out


def test_doctor_has_no_setup_line_when_everything_is_ready(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "discover_registry", _doctor_report())
    _run("doctor")
    assert "To set up local data" not in capsys.readouterr().out
