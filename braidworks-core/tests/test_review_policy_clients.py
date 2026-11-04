"""The 0.12 review default and explicit opt-in survive human client boundaries."""

import json

import pytest
from braidworks.core import FetchResult, ReviewPolicy, cli, fetch
from braidworks.core.registry import BraidRegistry
from braidworks.core.result import CandidateResult
from braidworks.core.strand import Strand
from helpers import ScriptedWeaver, ambiguous_result, simple_capability

QUERY = "protein.query"
ID = "protein.uniprot.accession"


def registry():
    cap = simple_capability("resolve", {QUERY}, {ID})
    candidates = (
        CandidateResult(strands=(Strand(ID, "P1"),), confidence=0.9),
        CandidateResult(strands=(Strand(ID, "P2"),), confidence=0.7),
    )

    def resolve(ss, backend, requested):
        result = ambiguous_result(requested, *candidates)
        result.warnings = ("Check species before accepting the match",)
        return result

    reg = BraidRegistry()
    reg.register(ScriptedWeaver(resolve, capability=cap))
    return reg


@pytest.mark.parametrize(
    "options,status,exit_code",
    [
        ([], "review", 0),
        (["--strict"], "review", 1),
        (["--review-policy", "allow_continue"], "resolved", 0),
        (["--review-policy", "allow_continue", "--strict"], "resolved", 1),
        (["--review-policy", "allow_continue", "--confidence-threshold", "0.95"], "review", 0),
    ],
)
def test_cli_review_default_selection_and_confidence_floor(
    monkeypatch, capsys, options, status, exit_code
):
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda **kw: registry())
    result = cli.main(
        ["weave", "--have", QUERY + "=TP53", "--want", ID, "--format", "json", *options]
    )
    row = json.loads(capsys.readouterr().out)[0]
    assert result == exit_code and row["status"] == status
    assert row["requires_review"]
    assert "Check species before accepting the match" in row["warnings"]
    if status == "review":
        assert len(row["candidates"]) == 2 and ID not in row["values"]
    else:
        assert row["values"][ID] == "P1"


def test_fetch_default_keeps_candidates_and_opt_in_keeps_review_flag():
    result = fetch(ID, ["TP53"], have=QUERY, registry=registry())
    assert not result.resolved and result.unresolved == ["TP53"]
    assert result.review_required == ["TP53"]
    assert len(result.review_queue[0].triggering_result.candidates) == 2
    restored = FetchResult.from_json(json.loads(json.dumps(result.to_json())))
    assert len(restored.review_queue[0].triggering_result.candidates) == 2
    assert restored.review_required == ["TP53"]
    selected = fetch(
        ID, ["TP53"], have=QUERY, registry=registry(), review_policy=ReviewPolicy.ALLOW_CONTINUE
    )
    assert selected.get("TP53")[ID] == "P1" and selected.review_required == ["TP53"]
    guarded = fetch(
        ID,
        ["TP53"],
        have=QUERY,
        registry=registry(),
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
        confidence_threshold=0.95,
    )
    assert not guarded.resolved and len(guarded.review_queue) == 1
