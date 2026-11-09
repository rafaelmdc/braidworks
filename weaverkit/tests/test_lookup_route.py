"""The route panel (3.5): what ran, in order, and what each step did; the graph is opt-in."""

from __future__ import annotations

import asyncio

from braidworks.core import Strand, StrandSet
from braidworks.core.executor import ExecutionError, ExecutionResult
from braidworks.core.strand import StepOutcome
from test_serve_parameters import QUERY, SYMBOL
from test_serve_parameters import recording_registry as _recording_fixture
from weaverkit._lookup_ui import render_lookup_page

from weaverkit import serve

recording_registry = _recording_fixture


def _row(name, *steps):
    ss = StrandSet.from_strands(name, [Strand("x", name)])
    ss.completion = [StepOutcome(cid, backend, status) for cid, backend, status in steps]
    return ss


def test_step_outcomes_count_statuses_backends_and_errors():
    found = _row("a", ("resolve", "api", "ok"), ("describe", "local", "ok"))
    empty = _row("b", ("resolve", "api", "ok"), ("describe", "local", "no_match"))
    failed = _row("c", ("resolve", "api", "ok"))
    raw = ExecutionResult(
        resolved=[found],
        unresolved=[(empty, None)],
        errors=[
            ExecutionError(failed, "WeaverError", "503", capability_id="describe"),
            ExecutionError(
                found, "WeaverError", "timeout", capability_id="resolve", recovered=True
            ),
        ],
    )
    outcomes = serve.step_outcomes(raw)
    # three final rows ran resolve (the failed row too); the recovered error is a note
    assert outcomes["resolve"] == {
        "statuses": {"ok": 3},
        "backends": {"api": 3},
        "errors": 0,
        "recovered": 1,
    }
    assert outcomes["describe"]["statuses"] == {"ok": 1, "no_match": 1}
    assert outcomes["describe"]["backends"] == {"local": 2}
    assert outcomes["describe"]["errors"] == 1


def test_run_payload_carries_the_route_and_its_outcomes(recording_registry):
    registry, _ = recording_registry
    batch = {"text": "TP53\nBRCA1", "format": "lines", "input_type": QUERY}
    payload = asyncio.run(serve.execute_query_response(registry, {}, [SYMBOL], [], batch))
    steps = [step["capability_id"] for step in payload["planned_routes"][0]["steps"]]
    assert steps == ["resolve", "describe"]
    assert payload["step_outcomes"]["resolve"]["statuses"] == {"ok": 2}
    assert set(payload["step_outcomes"]) == set(steps)


def test_traversal_payload_names_its_steps(recording_registry):
    registry, _ = recording_registry
    payload = serve.run_traversed_response(registry, {QUERY: "TP53"}, [SYMBOL], ["list_children"])
    assert payload["traverse"] == ["list_children"]
    assert "list_children" in payload["step_outcomes"]


def test_page_has_the_route_panel_and_links_the_graph(recording_registry):
    registry, _ = recording_registry
    page = render_lookup_page(registry)
    assert 'id="routecard"' in page and "How this was answered" in page
    assert page.count('href="/explore"') >= 2  # nav + "see these sources on the network"


def test_explore_links_back_to_the_form(monkeypatch, recording_registry, tmp_path):
    from test_serve_parameters import client_for

    registry, _ = recording_registry
    page = client_for(monkeypatch, registry, data_dir=tmp_path).get("/explore").text
    assert '<a href="/"' in page and "Look up" in page
