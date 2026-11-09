"""The results view (3.4): inline review without a run store, downloads, citations."""

from __future__ import annotations

from dataclasses import replace

import pytest
from braidworks.core import CandidateResult, Strand, WeaveStatus
from test_serve_parameters import GENE, QUERY, SYMBOL, client_for
from test_serve_parameters import recording_registry as _recording_fixture
from weaverkit._lookup_ui import render_lookup_page

from weaverkit import serve

recording_registry = _recording_fixture


@pytest.fixture
def reviewing(recording_registry):
    """`resolve` is ambiguous for every query (two candidates); later steps run normally."""
    registry, weaver = recording_registry
    original = weaver.execute

    async def ambiguous(cid, ss, **kwargs):
        result = await original(cid, ss, **kwargs)
        if cid == "resolve":
            return replace(
                result,
                status=WeaveStatus.AMBIGUOUS,
                strands=(),
                candidates=(
                    CandidateResult((Strand(GENE, 7157),), 0.9),
                    CandidateResult((Strand(GENE, 22059),), 0.6),
                ),
            )
        return result

    weaver.execute = ambiguous
    return registry


def _paused(client, text="TP53\nBRCA1"):
    body = {"batch": {"format": "lines", "input_type": QUERY, "text": text}, "want": [SYMBOL]}
    payload = client.post("/api/run", json=body).json()
    assert payload["ok"]
    return payload


def _decision(key, action, index=None):
    return {"version": 1, "entity_key": key, "action": action, "candidate_index": index}


def test_paused_rows_come_with_candidates_and_a_review_token(monkeypatch, reviewing, tmp_path):
    payload = _paused(client_for(monkeypatch, reviewing, data_dir=tmp_path))
    review = payload["table"]["review"]
    assert [item["input"] for item in review] == ["TP53", "BRCA1"]
    assert all(item["ambiguous"] and len(item["candidates"]) == 2 for item in review)
    assert review[0]["candidates"][0]["values"] == {GENE: 7157}
    assert payload["review_token"]
    assert [row["status"] for row in payload["table"]["rows"]] == ["review", "review"]


def test_review_choices_resume_the_paused_rows(monkeypatch, reviewing, tmp_path):
    client = client_for(monkeypatch, reviewing, data_dir=tmp_path)
    paused = _paused(client)
    first, second = (item["key"] for item in paused["table"]["review"])
    resumed = client.post(
        "/api/review",
        json={
            "token": paused["review_token"],
            "decisions": [_decision(first, "select", 0), _decision(second, "reject")],
        },
    ).json()
    assert resumed["ok"], resumed
    rows = resumed["table"]["rows"]
    assert [(row["input"], row["status"]) for row in rows] == [
        ("TP53", "resolved"),
        ("BRCA1", "unresolved"),
    ]
    assert rows[0][SYMBOL] is not None
    assert "review_token" not in resumed and resumed["table"]["review"] == []
    assert resumed["exports"]["csv"].splitlines()[1].startswith("TP53,1,resolved")


def test_undecided_rows_stay_paused_with_a_new_token(monkeypatch, reviewing, tmp_path):
    client = client_for(monkeypatch, reviewing, data_dir=tmp_path)
    paused = _paused(client)
    first = paused["table"]["review"][0]["key"]
    resumed = client.post(
        "/api/review",
        json={"token": paused["review_token"], "decisions": [_decision(first, "reject")]},
    ).json()
    assert [row["status"] for row in resumed["table"]["rows"]] == ["unresolved", "review"]
    assert resumed["review_token"] and resumed["review_token"] != paused["review_token"]
    # the old token was used up
    again = client.post(
        "/api/review",
        json={"token": paused["review_token"], "decisions": [_decision(first, "reject")]},
    ).json()
    assert not again["ok"] and "run the query again" in again["error"]


@pytest.mark.parametrize(
    ("decision", "message"),
    [
        (lambda key: _decision("not-a-key", "reject"), "no paused row"),
        (lambda key: _decision(key, "select", 5), "candidate index"),
        (lambda key: _decision(key, "accept"), "ambiguous"),
    ],
)
def test_bad_choices_are_refused_and_keep_the_review(
    monkeypatch, reviewing, tmp_path, decision, message
):
    client = client_for(monkeypatch, reviewing, data_dir=tmp_path)
    paused = _paused(client, "TP53")
    key = paused["table"]["review"][0]["key"]
    token = paused["review_token"]
    refused = client.post("/api/review", json={"token": token, "decisions": [decision(key)]})
    assert not refused.json()["ok"] and message in refused.json()["error"]
    kept = client.post(
        "/api/review", json={"token": token, "decisions": [_decision(key, "select", 0)]}
    ).json()
    assert kept["ok"] and kept["table"]["rows"][0]["status"] == "resolved"


def test_review_needs_at_least_one_choice(monkeypatch, reviewing, tmp_path):
    client = client_for(monkeypatch, reviewing, data_dir=tmp_path)
    paused = _paused(client, "TP53")
    refused = client.post("/api/review", json={"token": paused["review_token"]}).json()
    assert not refused["ok"] and "at least one" in refused["error"]


def test_held_reviews_are_bounded(monkeypatch, reviewing, tmp_path):
    monkeypatch.setattr(serve, "PAUSED_LIMIT", 2)
    monkeypatch.setattr(serve, "_PAUSED", type(serve._PAUSED)())
    client = client_for(monkeypatch, reviewing, data_dir=tmp_path)
    tokens = [_paused(client, "TP53")["review_token"] for _ in range(3)]
    assert list(serve._PAUSED) == tokens[1:]


def test_resolved_runs_hold_nothing(monkeypatch, recording_registry, tmp_path):
    registry, _ = recording_registry
    monkeypatch.setattr(serve, "_PAUSED", type(serve._PAUSED)())
    payload = _paused(client_for(monkeypatch, registry, data_dir=tmp_path), "TP53")
    assert "review_token" not in payload and not serve._PAUSED


def test_results_view_has_filters_downloads_review_and_citations(recording_registry):
    registry, _ = recording_registry
    page = render_lookup_page(registry)
    for element in (
        'data-export="csv"',
        'data-export="tsv"',
        'data-export="json"',
        'id="counts"',
        'id="resume"',
        "/api/review",
        'id="cites"',
    ):
        assert element in page, element
