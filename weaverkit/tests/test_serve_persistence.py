"""Browser endpoint contracts share operational options and durable execution."""

import json
import runpy
import shlex

from braidworks.core import QueryPersistence, cli
from braidworks.core.run_store import SQLiteRunStore
from test_serve_parameters import QUERY, SYMBOL, client_for
from test_serve_parameters import recording_registry as _recording_fixture

from weaverkit import serve

recording_registry = _recording_fixture


def test_browser_cache_run_status_and_resume(monkeypatch, recording_registry, tmp_path):
    registry, weaver = recording_registry
    client = client_for(monkeypatch, registry)
    options = QueryPersistence(str(tmp_path / "cache.sqlite"), str(tmp_path / "runs.sqlite"), "one")
    body = {"have": {QUERY: "TP53"}, "want": [SYMBOL], "persistence": options.to_json()}
    first = client.post("/api/run", json=body).json()
    assert first["ok"] and first["run"]["status"] == "complete"
    assert "owner" not in first["run"]
    calls = list(weaver.calls)
    body["persistence"]["run_id"] = "two"
    second = client.post("/api/run/stream", json=body)
    events = [json.loads(frame[6:]) for frame in second.text.strip().split("\n\n")]
    assert events[-1]["event"] == "done" and events[-1]["run"]["run_id"] == "two"
    assert any(event["event"] == "checkpoint" for event in events)
    assert weaver.calls == calls
    listed = client.get("/api/runs", params={"run_db": options.run_db}).json()
    assert [run["run_id"] for run in listed["runs"]] == ["one", "two"]
    status = client.get(
        "/api/run/status", params={"run_db": options.run_db, "run_id": "one"}
    ).json()
    assert status["run"]["status"] == "complete"
    resumed = client.post(
        "/api/resume", json={"run_id": "one", "persistence": options.to_json()}
    ).json()
    assert resumed["result"] == first["result"]
    assert resumed["rows"] == first["rows"] and weaver.calls == calls
    assert (
        client.post(
            "/api/resume",
            json={"run_id": "one", "persistence": options.to_json(), "want": ["changed"]},
        ).status_code
        == 422
    )


def test_generated_code_preserves_paths_policy_and_creates_runs(
    monkeypatch, recording_registry, tmp_path, capsys
):
    import braidworks.core
    from braidworks.core import CachePolicy

    registry, weaver = recording_registry
    options = QueryPersistence(
        str(tmp_path / "cache file.sqlite"),
        str(tmp_path / "runs file.sqlite"),
        "python-example",
        CachePolicy(60, 5, 4096),
        30,
    )
    document = serve.code_response(
        registry, {QUERY: "TP53"}, [SYMBOL], persistence=options.to_json()
    )
    assert document["ok"] and not weaver.calls
    tokens = shlex.split(document["artifacts"]["cli_weave"])
    assert tokens[tokens.index("--cache-db") + 1] == options.cache_db
    assert tokens[tokens.index("--cache-positive-ttl") + 1] == "60"
    monkeypatch.setattr(braidworks.core, "build_registry_from_entry_points", lambda: registry)
    script = tmp_path / "generated.py"
    script.write_text(document["artifacts"]["python"])
    runpy.run_path(str(script))
    assert len(json.loads(capsys.readouterr().out)["resolved"]) == 1
    store = SQLiteRunStore(options.run_db, create=False)
    assert store.load("python-example").status == "complete"
    tokens[tokens.index("--run-id") + 1] = "cli-example"
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    assert cli.main(tokens[1:] + ["--format", "json"]) == 0
    assert store.load("cli-example").status == "complete"


def test_status_missing_path_and_bad_options_fail_without_lookup(
    monkeypatch, recording_registry, tmp_path
):
    registry, weaver = recording_registry
    client = client_for(monkeypatch, registry)
    path = tmp_path / "missing.sqlite"
    assert not client.get("/api/runs", params={"run_db": str(path)}).json()["ok"]
    assert not path.exists()
    for options in (
        {"version": 999},
        {"version": 1, "lease_seconds": 0},
        {"version": 1, "cache_policy": "invalid"},
    ):
        response = client.post(
            "/api/run", json={"have": {QUERY: "TP53"}, "want": [SYMBOL], "persistence": options}
        )
        assert not response.json()["ok"]
    assert not weaver.calls


def test_browser_explicit_review_decisions(monkeypatch, recording_registry, tmp_path):
    from dataclasses import replace

    from braidworks.core import CandidateResult, Strand, WeaveStatus
    from test_serve_parameters import GENE

    registry, weaver = recording_registry
    original = weaver.execute

    async def reviewed(cid, ss, **kwargs):
        result = await original(cid, ss, **kwargs)
        if cid == "resolve":
            return replace(
                result,
                status=WeaveStatus.AMBIGUOUS,
                strands=(),
                candidates=(CandidateResult((Strand(GENE, 7157),), 0.9),),
            )
        return replace(result, requires_review=True) if cid == "describe" else result

    weaver.execute = reviewed
    client = client_for(monkeypatch, registry)
    options = QueryPersistence(run_db=str(tmp_path / "runs.sqlite"), run_id="review")
    body = {
        "batch": {"format": "lines", "input_type": QUERY, "text": "TP53\nTP53"},
        "want": [SYMBOL],
        "persistence": options.to_json(),
    }
    paused = client.post("/api/run", json=body).json()
    assert paused["ok"] and paused["run"]["status"] == "review"
    keys = [item["strand_set"]["execution_key"] for item in paused["run"]["reviews"]]
    resume = {
        "run_id": "review",
        "persistence": options.to_json(),
        "decisions": [
            {"version": 1, "entity_key": keys[0], "action": "select", "candidate_index": 0},
            {"version": 1, "entity_key": keys[1], "action": "reject"},
        ],
    }
    response = client.post("/api/resume/stream", json=resume)
    events = [json.loads(frame[6:]) for frame in response.text.strip().split("\n\n")]
    assert events[-1]["run"]["status"] == "review"
    assert {row["status"] for row in events[-1]["rows"]} == {"review", "unresolved"}
    resume["decisions"] = [{"version": 1, "entity_key": keys[0], "action": "accept"}]
    finished = client.post("/api/resume", json=resume).json()
    assert finished["ok"] and finished["run"]["status"] == "complete"
    assert {row["status"] for row in finished["rows"]} == {"resolved", "unresolved"}
