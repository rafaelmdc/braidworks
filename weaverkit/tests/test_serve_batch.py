"""Browser batches preserve the CLI's row and execution contracts."""

import json
import runpy

import pytest
from braidworks.core import cli
from test_serve_parameters import QUERY, SYMBOL, client_for

from weaverkit import serve

pytest_plugins = ["test_serve_parameters"]


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "fmt,text",
    [
        ("lines", "TP53\nTP53\nBRCA1"),
        ("csv", "protein.query\nTP53\nTP53\nBRCA1"),
        ("tsv", "protein.query\nTP53\nTP53\nBRCA1"),
    ],
)
def test_batch_rows_survive_execution_and_exports(
    monkeypatch, recording_registry, stream, fmt, text
):
    registry, weaver = recording_registry
    client = client_for(monkeypatch, registry)
    body = {
        "batch": {"text": text, "format": fmt, "input_type": QUERY},
        "want": [SYMBOL],
        "params": {"resolve": {"organism": "9606"}},
    }
    response = client.post("/api/run/stream" if stream else "/api/run", json=body)
    if stream:
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        assert events[-1]["event"] == "done"
        payload = events[-1]
    else:
        payload = response.json()
    assert payload["ok"]
    assert payload["summary"]["inputs"] == 3
    assert sorted(row["source_row"] for row in payload["rows"]) == [1, 2, 3]
    assert len({row["outcome"] for row in payload["rows"]}) == 3
    assert all(params == {"organism": 9606} for cid, params in weaver.calls if cid == "resolve")


def test_batch_traversal_uses_one_global_expansion_budget(monkeypatch, recording_registry):
    registry, _ = recording_registry
    response = client_for(monkeypatch, registry).post(
        "/api/run/stream",
        json={
            "batch": {"text": "TP53\nBRCA1", "format": "lines", "input_type": QUERY},
            "want": [SYMBOL],
            "traverse": ["list_children"],
            "expand": "all",
            "max_expansion": 3,
        },
    )
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert events[-1]["event"] == "done"
    assert events[-1]["summary"]["inputs"] == 2
    assert len(events[-1]["rows"]) <= 3
    assert events[-1]["result"]["truncations"]


@pytest.mark.parametrize(
    "batch",
    [
        {"format": "lines", "text": ""},
        {"format": "csv", "text": "protein.query,protein.query\na,b"},
        {"format": "csv", "text": "protein.query\na,b"},
    ],
)
def test_invalid_batch_rejected_before_io(monkeypatch, recording_registry, batch):
    registry, weaver = recording_registry
    response = client_for(monkeypatch, registry).post(
        "/api/run", json={"batch": batch, "want": [SYMBOL]}
    )
    assert not response.json()["ok"]
    assert not weaver.calls


def test_batch_generated_python_reproduces_all_rows(
    monkeypatch, recording_registry, capsys, tmp_path
):
    registry, _ = recording_registry
    document = serve.batch_code_response(
        registry,
        {},
        [SYMBOL],
        [],
        {"text": "TP53\nBRCA1", "format": "lines", "input_type": QUERY},
        params={"resolve": {"organism": "9606"}},
    )
    assert document["ok"]
    import braidworks.core

    monkeypatch.setattr(braidworks.core, "build_registry_from_entry_points", lambda: registry)
    script = tmp_path / "generated-batch.py"
    script.write_text(document["artifacts"]["python"])
    runpy.run_path(str(script))
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["resolved"]) == 2
    assert [row["source_row"] for row in payload["resolved"]] == [1, 2]
    assert "weaverkit.serve" not in document["artifacts"]["python"]
    assert "--in-file -" in document["artifacts"]["cli_weave"]


def test_browser_and_cli_share_table_parser(tmp_path):
    text = 'protein.query,gene.ncbi.id\n"TP53, human",\n,7157\n'
    path = tmp_path / "batch.csv"
    path.write_text(text)
    cli_rows = cli._rows_from_file(str(path), None)
    sets = serve.batch_inputs({}, {"text": text, "format": "csv"})
    assert [ss.available_types() for ss in sets] == [frozenset(row) for row in cli_rows]
    assert sets[0].get(QUERY).value == "TP53, human"


def test_every_heterogeneous_route_is_validated_before_io(monkeypatch, recording_registry):
    registry, weaver = recording_registry
    payload = (
        client_for(monkeypatch, registry)
        .post(
            "/api/run",
            json={
                "batch": {"format": "csv", "text": "protein.query,missing.key\nTP53,\n,value\n"},
                "want": [SYMBOL],
            },
        )
        .json()
    )
    assert not payload["ok"]
    assert not weaver.calls


def test_batch_exports_retain_mixed_terminal_outcomes(monkeypatch, recording_registry):
    from braidworks.core import WeaveResult, WeaveStatus

    registry, weaver = recording_registry
    original = weaver.execute

    async def mixed(cid, ss, **kwargs):
        query = ss.get(QUERY)
        if cid == "resolve" and query.value in {"MISS", "FAIL"}:
            return WeaveResult(
                cid,
                "1.0.0",
                kwargs["backend"],
                frozenset({"g"}),
                WeaveStatus.NO_MATCH if query.value == "MISS" else WeaveStatus.ERROR,
                errors=() if query.value == "MISS" else ("upstream failed",),
            )
        return await original(cid, ss, **kwargs)

    weaver.execute = mixed
    payload = (
        client_for(monkeypatch, registry)
        .post(
            "/api/run",
            json={
                "batch": {"format": "lines", "text": "TP53\nMISS\nFAIL", "input_type": QUERY},
                "want": [SYMBOL],
            },
        )
        .json()
    )
    assert payload["ok"]
    assert {row["status"] for row in payload["rows"]} == {"resolved", "unresolved", "error"}
    assert sorted(row["source_row"] for row in payload["rows"]) == [1, 2, 3]
