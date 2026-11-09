"""Rows say why a requested field is missing: a failed, empty or unreached step."""

from __future__ import annotations

import braidworks as bw
import pytest
from braidworks.core import cli
from braidworks.core.exceptions import BackendUnavailable
from braidworks.core.outcomes import missing_reasons
from braidworks.core.result import WeaveResult, WeaveStatus
from tests.test_api import DOWN_CAP, UP_CAP, ClosingWeaver, _down, _registry, _up

WANT = ["protein.name", "structure.pdb.ids"]


def _registry_with(down):
    registry = _registry()
    replaced = type(registry)()
    replaced.register(ClosingWeaver(_up, capability=UP_CAP, weaver_id="uniprot"))
    replaced.register(ClosingWeaver(down, capability=DOWN_CAP, weaver_id="pdbe"))
    return replaced


def _no_structures(ss, backend, requested):
    if ss.get("protein.uniprot.accession").value == "ACC_EMPTY":
        return WeaveResult(
            "list_structures", "1.0.0", backend, frozenset({"g"}), status=WeaveStatus.NO_MATCH
        )
    return _down(ss, backend, requested)


def _not_set_up(ss, backend, requested):
    raise BackendUnavailable("backend 'api' is not configured for 'pdbe'")


def _get(down, ids):
    with bw.Session(registry=_registry_with(down)) as session:
        return session.get(ids, have="protein.query", want=WANT)


def test_complete_rows_have_no_reason_and_no_column():
    result = _get(_down, ["P1"])
    assert "why_missing" not in result.rows[0]
    assert "why_missing" not in result.columns
    assert result.to_csv().splitlines()[0].endswith(",missing")


def test_a_source_with_no_match_is_named():
    result = _get(_no_structures, ["EMPTY", "P1"])
    empty, full = result.rows
    assert empty["status"] == "resolved"
    assert empty["why_missing"] == {"structure.pdb.ids": "pdbe has no match"}
    assert "why_missing" not in full
    header, first, second = result.to_csv().splitlines()
    assert header.endswith(",missing,why_missing")
    assert first.endswith(",structure.pdb.ids,structure.pdb.ids: pdbe has no match")
    assert second.endswith(",,")  # the complete row leaves both cells empty


def test_a_source_that_is_not_set_up_says_so():
    result = _get(_not_set_up, ["P1"])
    row = result.rows[0]
    assert row["protein.name"] == "Name of P1"
    assert row["why_missing"] == {
        "structure.pdb.ids": "pdbe is not set up on this machine (run `braidworks doctor`)"
    }
    assert result.to_json()["rows"][0]["why_missing"] == row["why_missing"]


def test_unresolved_rows_rely_on_their_status():
    result = _get(_down, ["MISS"])
    assert result.rows[0]["status"] == "unresolved"
    assert "why_missing" not in result.rows[0]


def _record(status, completion, diagnostics=()):
    return {
        "status": status,
        "missing": ["b", "c"],
        "completion": completion,
        "diagnostics": list(diagnostics),
    }


PRODUCERS = {"b": [("src", "step_b")], "c": [("other", "step_c")]}


def test_reasons_for_unreached_failed_and_silent_steps():
    record = _record(
        "resolved",
        [
            {"capability_id": "step_b", "status": "error"},
            {"capability_id": "step_c", "status": "skipped"},
        ],
        [{"capability_id": "step_b", "category": "timeout", "recovered": False}],
    )
    reasons = missing_reasons(record, PRODUCERS)
    assert "did not respond in time" in reasons["b"] and reasons["b"].startswith("src ")
    assert reasons["c"].startswith("other was not reached")
    silent = _record("error", [{"capability_id": "step_b", "status": "ok"}])
    assert missing_reasons(silent, PRODUCERS) == {"b": "src returned no value"}


@pytest.mark.parametrize("status", ["unresolved", "review"])
def test_statuses_that_already_explain_get_no_reason(status):
    record = _record(status, [{"capability_id": "step_b", "status": "no_match"}])
    assert missing_reasons(record, PRODUCERS) == {}


def test_human_output_prints_the_reason(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "build_registry_from_entry_points", lambda only=None: _registry_with(_no_structures)
    )
    assert cli.main(["get", "EMPTY", "--have", "protein.query", "--want", ",".join(WANT)]) == 0
    assert "why: structure.pdb.ids: pdbe has no match" in capsys.readouterr().out
