"""Species refinements must survive every browser request path, before backend I/O."""

import json
import runpy
import shlex
from types import SimpleNamespace

import pytest
from braidworks.core import (
    BaseWeaver,
    BraidRegistry,
    Capability,
    OutputGroup,
    Parameter,
    Strand,
    WeaveResult,
    WeaverManifest,
    WeaveStatus,
)
from braidworks.core.executor import ExecutionError, ExecutionResult, ReviewQueueItem
from braidworks.core.result import CandidateResult
from braidworks.core.strand import StrandSet

from weaverkit import serve

QUERY = "protein.query"
GENE = "gene.ncbi.id"
SYMBOL = "gene.symbol"


@pytest.fixture
def recording_registry():
    def cap(name, consumes, produces, **kwargs):
        return Capability(
            name,
            frozenset(consumes),
            frozenset(produces),
            (OutputGroup("g", frozenset(produces)),),
            backends=("local",),
            **kwargs,
        )

    class Weaver(BaseWeaver):
        MANIFEST = WeaverManifest(
            "fixture",
            "1.0.0",
            (
                cap("resolve", {QUERY}, {GENE}, parameters=(Parameter("organism", type="int"),)),
                cap(
                    "list_children",
                    {GENE},
                    {GENE, "gene.child.count"},
                    set_outputs=frozenset({GENE}),
                ),
                cap("describe", {GENE}, {SYMBOL, "go.biological_process"}),
            ),
        )

        def __init__(self):
            self.calls = []
            self.child_ids = [100, 101]

        def backend_fingerprint(self, backend):
            return "fixture-v1"

        async def execute(self, cid, ss, *, requested_outputs, backend, params=None):
            self.calls.append((cid, params))
            values = {
                "resolve": {GENE: 7157},
                "list_children": {GENE: self.child_ids, "gene.child.count": len(self.child_ids)},
                "describe": {SYMBOL: "child", "go.biological_process": ["DNA repair"]},
            }[cid]
            return WeaveResult(
                cid,
                "1.0.0",
                backend,
                frozenset({"g"}),
                WeaveStatus.OK,
                strands=tuple(Strand(key, value) for key, value in values.items()),
            )

    weaver = Weaver()
    registry = BraidRegistry()
    registry.register(weaver)
    return registry, weaver


def client_for(monkeypatch, registry):
    testclient = pytest.importorskip("fastapi.testclient")
    monkeypatch.setattr(serve, "discover_registry", lambda: SimpleNamespace(registry=registry))
    return testclient.TestClient(serve.create_app())


@pytest.mark.parametrize("expand,k,expected", [("top", 3, 1), ("top_k", 3, 3), ("all", 3, 5)])
@pytest.mark.parametrize("stream", [False, True])
def test_browser_expansion_modes_keep_identifiable_leaves(
    monkeypatch, recording_registry, expand, k, expected, stream
):
    registry, weaver = recording_registry
    weaver.child_ids = list(range(100, 105))
    client = client_for(monkeypatch, registry)
    if stream:
        # Ordinary self-loop fan-out needs an explicit traversal to select the list.
        # SSE currently runs ordinary plans; graph POST owns explicit traversal.
        # Request the set count as an additional target to include the list operation.
        response = client.get(
            "/api/run/stream",
            params={
                "have": json.dumps({GENE: 7157}),
                "want": "gene.child.count,gene.symbol",
                "expand": expand,
                "k": k,
            },
        )
        payload = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ][-1]
        assert payload["event"] == "done"
    else:
        payload = client.post(
            "/api/run",
            json={
                "have": {GENE: "7157"},
                "want": [SYMBOL],
                "traverse": ["list_children"],
                "expand": expand,
                "k": k,
            },
        ).json()
    assert payload["ok"]
    assert len(payload["rows"]) == expected
    assert len({row[GENE] for row in payload["rows"]}) == expected


@pytest.mark.parametrize("stream", [False, True])
def test_species_parameter_reaches_typed_and_graph_run(monkeypatch, recording_registry, stream):
    registry, weaver = recording_registry
    client = client_for(monkeypatch, registry)
    params = {"resolve": {"organism": "9606"}}
    if stream:
        response = client.get(
            "/api/run/stream",
            params={
                "have": json.dumps({QUERY: "TP53"}),
                "want": SYMBOL,
                "params": json.dumps(params),
            },
        )
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        payload = next(event for event in events if event["event"] == "done")
    else:
        payload = client.post(
            "/api/run", json={"have": {QUERY: "TP53"}, "want": [SYMBOL], "params": params}
        ).json()
    assert payload["ok"]
    assert weaver.calls[0] == ("resolve", {"organism": 9606})
    assert payload["effective_params"]["resolve"]["organism"] == 9606


def test_traversal_plan_exposes_and_applies_resolver_species(monkeypatch, recording_registry):
    registry, weaver = recording_registry
    client = client_for(monkeypatch, registry)
    plan = client.post(
        "/api/plan",
        json={"from_types": [QUERY], "to_types": [SYMBOL], "traverse": ["list_children"]},
    ).json()
    assert plan["ok"]
    assert "organism" in [
        p["name"] for cap in plan["parameter_capabilities"] for p in cap["parameters"]
    ]
    payload = client.post(
        "/api/run",
        json={
            "have": {QUERY: "TP53"},
            "want": [SYMBOL],
            "traverse": ["list_children"],
            "params": {"resolve": {"organism": "9606"}},
        },
    ).json()
    assert payload["ok"]
    assert weaver.calls[0] == ("resolve", {"organism": 9606})
    assert payload["effective_params"]["resolve"]["organism"] == 9606


@pytest.mark.parametrize("stream", [False, True])
def test_browser_rejects_wrong_scope_before_io(monkeypatch, recording_registry, stream):
    registry, weaver = recording_registry
    client = client_for(monkeypatch, registry)
    params = {"wrong": {"organism": "9606"}}
    if stream:
        response = client.get(
            "/api/run/stream",
            params={
                "have": json.dumps({QUERY: "TP53"}),
                "want": SYMBOL,
                "params": json.dumps(params),
            },
        )
        assert '"event": "error"' in response.text
    else:
        assert not client.post(
            "/api/run", json={"have": {QUERY: "TP53"}, "want": [SYMBOL], "params": params}
        ).json()["ok"]
    assert not weaver.calls


def test_generated_cli_and_python_reproduce_selected_experiment(
    monkeypatch, recording_registry, capsys, tmp_path
):
    import braidworks.core
    from braidworks.core import BackendPolicy, cli

    registry, weaver = recording_registry
    settings = {
        "have": {QUERY: "TP53"},
        "want": [SYMBOL],
        "traverse": ["list_children"],
        "params": {"resolve": {"organism": "9606"}},
        "expand": "all",
        "k": 2,
        "max_expansion": 1,
        "policy": BackendPolicy.LOCAL_ONLY,
    }
    document = serve.code_response(registry, **settings)
    assert document["ok"] and not weaver.calls
    command = shlex.split(document["artifacts"]["cli_weave"])
    monkeypatch.setattr(cli, "build_registry_from_entry_points", lambda only=None: registry)
    assert cli.main(command[1:] + ["--format", "json"]) == 0
    cli_rows = json.loads(capsys.readouterr().out)
    assert len(cli_rows) == 1 and cli_rows[0]["values"][SYMBOL] == "child"
    assert weaver.calls[0] == ("resolve", {"organism": 9606})
    weaver.calls.clear()
    monkeypatch.setattr(braidworks.core, "build_registry_from_entry_points", lambda: registry)
    script = tmp_path / "generated_experiment.py"
    script.write_text(document["artifacts"]["python"])
    runpy.run_path(str(script))
    python_result = json.loads(capsys.readouterr().out)
    assert len(python_result["resolved"]) == 1
    assert python_result["truncations"][0]["omitted"] == 1
    assert weaver.calls[0] == ("resolve", {"organism": 9606})


def test_unset_species_is_visible_in_effective_settings(recording_registry):
    registry, _ = recording_registry
    payload = serve.run_response(registry, {QUERY: "TP53"}, [SYMBOL])
    assert payload["effective_params"] == {"resolve": {"organism": None}}


def test_browser_rows_preserve_all_outcomes_and_review_candidates(recording_registry):
    registry, _ = recording_registry
    sets = [StrandSet.from_strands("same", [Strand(GENE, index)]) for index in range(4)]
    for index, ss in enumerate(sets, 1):
        ss.source_row = index
    sets[0].parent_id = "root"
    sets[0].add_strand(Strand(SYMBOL, "partial"))
    no_match = WeaveResult("describe", "1.0.0", "local", frozenset(), WeaveStatus.NO_MATCH)
    ambiguous = WeaveResult(
        "describe",
        "1.0.0",
        "local",
        frozenset(),
        WeaveStatus.AMBIGUOUS,
        candidates=(CandidateResult(strands=(Strand(SYMBOL, "choice"),)),),
    )
    result = ExecutionResult(
        resolved=[sets[0]],
        unresolved=[(sets[1], no_match)],
        review_queue=[ReviewQueueItem(sets[2], ambiguous, ())],
        errors=[ExecutionError(sets[3], "WeaverError", "503")],
    )
    payload = serve._traverse_payload(registry, result, [SYMBOL, "missing.field"], [])
    assert [row["status"] for row in payload["rows"]] == [
        "resolved",
        "unresolved",
        "review",
        "error",
    ]
    assert [row["source_row"] for row in payload["rows"]] == [1, 2, 3, 4]
    assert payload["rows"][0]["parent"] == "root"
    assert payload["rows"][0]["missing"] == ["missing.field"]
    assert payload["rows"][2]["candidates"][0]["strands"][0]["value"] == "choice"
    assert payload["rows"][3]["diagnostics"][0]["message"] == "503"
    assert payload["summary"]["total"] == 4 and payload["summary"]["review"] == 1
    assert GENE in payload["identity_columns"]


def test_graph_bound_reaches_traversal_and_reports_omissions(monkeypatch, recording_registry):
    registry, _ = recording_registry
    client = client_for(monkeypatch, registry)
    payload = client.post(
        "/api/run",
        json={
            "have": {GENE: "7157"},
            "want": [SYMBOL],
            "traverse": ["list_children"],
            "max_expansion": 1,
            "expand": "all",
        },
    ).json()
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["truncations"][0]["omitted"] == 1
    assert payload["summary"]["truncated_forks"] == 1


@pytest.mark.parametrize("params", ["[]", '{"resolve": []}', '{"resolve": "9606"}'])
def test_sse_malformed_parameters_are_reported_as_error_events(
    monkeypatch, recording_registry, params
):
    registry, weaver = recording_registry
    client = client_for(monkeypatch, registry)
    response = client.get(
        "/api/run/stream",
        params={"have": json.dumps({QUERY: "TP53"}), "want": SYMBOL, "params": params},
    )
    assert '"event": "error"' in response.text
    assert not weaver.calls


@pytest.mark.parametrize("mode", ["typed", "graph", "traversal"])
@pytest.mark.parametrize(
    "policy,threshold,status",
    [
        ("halt", 0.0, "review"),
        ("allow_continue", 0.0, "resolved"),
        ("allow_continue", 0.95, "review"),
    ],
)
def test_browser_review_policy_and_confidence_floor(
    monkeypatch, recording_registry, mode, policy, threshold, status
):
    registry, weaver = recording_registry
    execute = weaver.execute

    async def ambiguous_resolve(cid, ss, **kwargs):
        result = await execute(cid, ss, **kwargs)
        if cid == "resolve":
            return WeaveResult(
                cid,
                "1.0.0",
                "local",
                frozenset({"g"}),
                WeaveStatus.AMBIGUOUS,
                candidates=(
                    CandidateResult(strands=(Strand(GENE, 7157),), confidence=0.9),
                    CandidateResult(strands=(Strand(GENE, 562),), confidence=0.7),
                ),
            )
        return result

    monkeypatch.setattr(weaver, "execute", ambiguous_resolve)
    client = client_for(monkeypatch, registry)
    request = {
        "have": {QUERY: "TP53"},
        "want": [SYMBOL],
        "review_policy": policy,
        "confidence_threshold": threshold,
    }
    if mode == "typed":
        response = client.get(
            "/api/run/stream",
            params={
                **request,
                "have": json.dumps(request["have"]),
                "want": SYMBOL,
            },
        )
        payload = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ][-1]
        assert payload["event"] == "done"
    else:
        if mode == "traversal":
            request["traverse"] = ["list_children"]
        payload = client.post("/api/run", json=request).json()
    assert payload["ok"], payload
    assert payload["review_policy"] == policy and payload["confidence_threshold"] == threshold
    assert {row["status"] for row in payload["rows"]} == {status}
    assert all(row["requires_review"] for row in payload["rows"])
    if status == "review":
        assert len(payload["rows"][0]["candidates"]) == 2
        assert [cid for cid, _ in weaver.calls] == ["resolve"]


def test_generated_code_preserves_review_policy_and_confidence(recording_registry):
    registry, _ = recording_registry
    document = serve.code_response(
        registry,
        {QUERY: "TP53"},
        [SYMBOL],
        review_policy="allow_continue",
        confidence_threshold=0.8,
    )
    assert document["ok"]
    assert "--review-policy allow_continue" in document["artifacts"]["cli_weave"]
    assert "--confidence-threshold 0.8" in document["artifacts"]["cli_weave"]
    assert "ReviewPolicy('allow_continue')" in document["artifacts"]["python"]
    assert "confidence_threshold=0.8" in document["artifacts"]["python"]
