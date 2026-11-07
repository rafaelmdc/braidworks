"""Every browser run goes through the same `Session` as Python and the CLI."""

from __future__ import annotations

import asyncio
import inspect

import braidworks as bw
import pytest
from braidworks._session import Session
from braidworks.core import QueryPersistence
from test_serve_parameters import QUERY, SYMBOL, client_for
from test_serve_parameters import recording_registry as _recording_fixture

from weaverkit import serve

recording_registry = _recording_fixture


@pytest.fixture
def executed(monkeypatch):
    """Record each Session._execute / _resume_run call while still running it."""
    calls = []
    execute, resume = Session._execute, Session._resume_run

    async def recording_execute(self, prepared, want, **kwargs):
        calls.append(("execute", sorted(prepared.request.targets), list(prepared.traversals)))
        return await execute(self, prepared, want, **kwargs)

    async def recording_resume(self, run_id, persistence, **kwargs):
        calls.append(("resume", run_id))
        return await resume(self, run_id, persistence, **kwargs)

    monkeypatch.setattr(Session, "_execute", recording_execute)
    monkeypatch.setattr(Session, "_resume_run", recording_resume)
    return calls


def test_plain_run_goes_through_session(recording_registry, executed):
    registry, _ = recording_registry
    assert serve.run_response(registry, {QUERY: "TP53"}, [SYMBOL])["ok"]
    assert executed == [("execute", [SYMBOL], [])]


def test_traversed_run_goes_through_session(recording_registry, executed):
    registry, _ = recording_registry
    payload = serve.run_traversed_response(registry, {QUERY: "TP53"}, [SYMBOL], ["list_children"])
    assert payload["ok"] and payload["path"] is None
    assert executed == [("execute", [SYMBOL], [("fixture", "list_children")])]


def test_batch_run_goes_through_session(recording_registry, executed):
    registry, _ = recording_registry
    batch = {"text": "TP53\nBRCA1\n", "format": "lines", "input_type": QUERY}
    payload = asyncio.run(serve.execute_batch_response(registry, {}, [SYMBOL], [], batch))
    assert payload["ok"] and payload["summary"]["inputs"] == 2
    assert executed == [("execute", [SYMBOL], [])]


def test_saved_run_streaming_and_resume_go_through_session(
    monkeypatch, recording_registry, executed, tmp_path
):
    registry, _ = recording_registry
    client = client_for(monkeypatch, registry, data_dir=tmp_path)
    options = QueryPersistence(None, str(tmp_path / "runs.sqlite"), "one").to_json()
    body = {"have": {QUERY: "TP53"}, "want": [SYMBOL], "persistence": options}
    assert client.post("/api/run", json=body).json()["run"]["status"] == "complete"
    stream = client.get(
        "/api/run/stream", params={"have": f'{{"{QUERY}": "TP53"}}', "want": SYMBOL}
    )
    assert '"event": "done"' in stream.text
    assert client.post("/api/resume", json={"run_id": "one", "persistence": options}).json()["ok"]
    assert executed == [("execute", [SYMBOL], []), ("execute", [SYMBOL], []), ("resume", "one")]


def test_streamed_runs_still_report_progress(monkeypatch, recording_registry, tmp_path):
    registry, _ = recording_registry
    client = client_for(monkeypatch, registry, data_dir=tmp_path)
    stream = client.get(
        "/api/run/stream", params={"have": f'{{"{QUERY}": "TP53"}}', "want": SYMBOL}
    )
    assert '"event": "progress"' in stream.text and '"completed_inputs": 0' in stream.text


def test_serve_has_no_second_execution_path():
    source = inspect.getsource(serve)
    for engine_call in ("execute_query(", "execute_managed_query(", "continue_run(", "start_run("):
        assert engine_call not in source, engine_call


# --- /api/find ----------------------------------------------------------------------


def test_find_response_ranks_like_bw_find(recording_registry):
    registry, _ = recording_registry
    with bw.Session(registry=registry) as session:
        expected = session.find("gene symbol", limit=3).to_json()
    assert serve.find_response(registry, "gene symbol", 3) == {"ok": True, "matches": expected}


@pytest.mark.parametrize(("text", "limit"), [("", 10), ("   ", 10), ("gene", 0), ("gene", 101)])
def test_find_response_rejects_bad_requests(recording_registry, text, limit):
    registry, _ = recording_registry
    payload = serve.find_response(registry, text, limit)
    assert not payload["ok"] and payload["error"]


def test_api_find_endpoint(monkeypatch, recording_registry, tmp_path):
    registry, _ = recording_registry
    client = client_for(monkeypatch, registry, data_dir=tmp_path)
    payload = client.get("/api/find", params={"q": "gene symbol", "limit": 2}).json()
    assert payload["ok"] and len(payload["matches"]) <= 2
    assert payload == serve.find_response(registry, "gene symbol", 2)
