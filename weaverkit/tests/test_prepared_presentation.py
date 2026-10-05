"""Presentation consumes prepared plans without replanning or touching sources."""

import asyncio
import shlex

from braidworks.core import BackendPolicy, Braider
from test_serve_parameters import QUERY, SYMBOL
from test_serve_parameters import recording_registry as _recording_fixture
from weaverkit.view import render_path

from weaverkit import serve

recording_registry = _recording_fixture


def test_render_prepared_braid_without_planner(monkeypatch, recording_registry):
    registry, weaver = recording_registry
    prepared = serve._prepare_experiment(registry, {QUERY: "TP53"}, [SYMBOL], [])

    def forbidden(*args, **kwargs):
        raise AssertionError("presentation must not replan")

    monkeypatch.setattr(Braider, "plan", forbidden)
    path = render_path(registry, prepared.plans[0][0], policy=BackendPolicy.LOCAL_FIRST)
    assert path["step_count"] == len(prepared.plans[0][0].steps)
    assert not weaver.calls


def test_preview_and_execution_plan_once(monkeypatch, recording_registry):
    registry, _ = recording_registry
    original = Braider.plan
    calls = []

    def counted(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Braider, "plan", counted)
    assert serve.plan_response(registry, [QUERY], [SYMBOL])["ok"]
    assert len(calls) == 1
    calls.clear()
    assert serve.run_response(registry, {QUERY: "TP53"}, [SYMBOL])["ok"]
    assert len(calls) == 1
    calls.clear()
    assert asyncio.run(serve.execute_batch_response(registry, {QUERY: "TP53"}, [SYMBOL], [], None))[
        "ok"
    ]
    assert len(calls) == 1


def test_codegen_quotes_shell_literals(recording_registry):
    registry, weaver = recording_registry
    value = "a' ; $(touch should-never-exist) `echo nope`"
    document = serve.code_response(registry, {QUERY: value}, [SYMBOL])
    assert document["ok"]
    tokens = shlex.split(document["artifacts"]["cli_weave"])
    assert tokens[tokens.index("--have") + 1] == f"{QUERY}={value}"
    compile(document["artifacts"]["python"], "generated.py", "exec")
    assert not weaver.calls
