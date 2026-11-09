"""Saved runs from Python: Session(runs=...), run_id, Session.resume and Session.runs."""

from __future__ import annotations

import braidworks as bw
import pytest
from braidworks.core.run_store import RunConflict
from tests.test_api import _registry

WANT = ["protein.name", "structure.pdb.ids"]


def _session(tmp_path):
    return bw.Session(registry=_registry(), runs=tmp_path / "runs.sqlite")


def test_a_query_becomes_a_named_saved_run(tmp_path):
    with _session(tmp_path) as s:
        result = s.get(["P1", "MISS"], have="protein.query", want=WANT, run_id="first")
        assert result.run_id == "first"
        assert [row["status"] for row in result.rows] == ["resolved", "unresolved"]
        [run] = s.runs()
        assert run["run_id"] == "first" and run["inputs"] == 2 and run["reviews"] == 0


def test_an_unnamed_run_gets_an_id(tmp_path):
    with _session(tmp_path) as s:
        result = s.get(["P1"], have="protein.query", want=WANT)
        assert result.run_id and [r["run_id"] for r in s.runs()] == [result.run_id]


def test_paused_rows_are_decided_in_a_later_session(tmp_path):
    with _session(tmp_path) as s:
        paused = s.get(["AMB", "P1"], have="protein.query", want=WANT, run_id="review-me")
        assert [row["status"] for row in paused.rows] == ["review", "resolved"]
        assert s.runs()[0]["reviews"] == 1

    with _session(tmp_path) as later:  # another process, another day
        reopened = later.resume("review-me")
        assert [row["status"] for row in reopened.rows] == ["review", "resolved"]
        assert reopened.want == WANT
        reopened.review[0].choose(1)
        done = reopened.resume()
        assert done.run_id == "review-me"
        assert [row["status"] for row in done.rows] == ["resolved", "resolved"]
        assert done.rows[0]["protein.name"] == "Candidate B"
        assert later.runs()[0]["reviews"] == 0

    with _session(tmp_path) as again:  # the decision was saved with the run
        assert again.resume("review-me").rows[0]["protein.name"] == "Candidate B"


def test_existing_run_ids_are_never_overwritten(tmp_path):
    with _session(tmp_path) as s:
        s.get(["P1"], have="protein.query", want=WANT, run_id="same")
        with pytest.raises(RunConflict, match="already exists"):
            s.get(["P2"], have="protein.query", want=WANT, run_id="same")


def test_run_features_need_a_run_store():
    with bw.Session(registry=_registry()) as s:
        with pytest.raises(ValueError, match="run store"):
            s.get(["P1"], have="protein.query", want=WANT, run_id="x")
        with pytest.raises(ValueError, match="run store"):
            s.resume("x")
        with pytest.raises(ValueError, match="run store"):
            s.runs()
        assert s.get(["P1"], have="protein.query", want=WANT).run_id is None
