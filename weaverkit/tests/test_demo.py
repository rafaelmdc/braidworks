"""Offline demo (4.2): fixture-backed sources, canned queries, a labelled browser."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest
from test_serve_parameters import GENE, QUERY, SYMBOL
from test_serve_parameters import recording_registry as _recording_fixture
from weaverkit._lookup_ui import render_lookup_page
from weaverkit.demo import DEMOS, NOTICE, Demo, demo_registry, find_demo, runnable
from weaverkit.view import build_data

from weaverkit import demo, serve

recording_registry = _recording_fixture

TOY = Demo(
    name="toy",
    title="Symbols of a gene",
    ids=("TP53",),
    have=QUERY,
    want=(SYMBOL,),
    params={"resolve": {"organism": "9606"}},
)


def _entry(name, value):
    return SimpleNamespace(name=name, value=value)


@pytest.fixture
def plugins(monkeypatch, recording_registry):
    """Three installed sources: one with a fixture builder, one without, one broken."""
    _, weaver = recording_registry
    built = []

    def build_fixture():
        built.append("fixture")
        return weaver

    module = types.ModuleType("toy_weaver_factory")
    module.build_toy = lambda: pytest.fail("the live builder must not run in a demo")
    module.build_toy_fixture = build_fixture
    plain = types.ModuleType("plain_weaver_factory")
    plain.build_plain = lambda: pytest.fail("a source without a fixture stays out")
    monkeypatch.setitem(sys.modules, "toy_weaver_factory", module)
    monkeypatch.setitem(sys.modules, "plain_weaver_factory", plain)
    entries = [
        _entry("toy", "toy_weaver_factory:build_toy"),
        _entry("plain", "plain_weaver_factory:build_plain"),
        _entry("broken", "no_such_module_for_demo:build"),
    ]
    monkeypatch.setattr(demo.importlib.metadata, "entry_points", lambda group: entries)
    return weaver, built


def test_demo_registry_uses_only_fixture_builders(plugins):
    _, built = plugins
    registry = demo_registry()
    assert [m.weaver_id for m in registry.manifests()] == ["fixture"]
    assert built == ["fixture"]


def test_only_routable_demos_are_offered(recording_registry):
    registry, _ = recording_registry
    unreachable = Demo("far", "Far", ("x",), QUERY, ("structure.pdb.ids",))
    assert [d.name for d in runnable(registry)] == []  # none of the real demos route here
    monkey = (TOY, unreachable)
    original = demo.DEMOS
    try:
        demo.DEMOS = monkey
        assert [d.name for d in runnable(registry)] == ["toy"]
    finally:
        demo.DEMOS = original


def test_run_answers_from_the_fixtures(plugins, monkeypatch):
    weaver, _ = plugins
    monkeypatch.setattr(demo, "DEMOS", (TOY,))
    [(item, result)] = demo.run("toy")
    assert item is TOY
    assert [(row["input"], row["status"], row[SYMBOL]) for row in result.rows] == [
        ("TP53", "resolved", "child")
    ]
    assert ("resolve", {"organism": 9606}) in weaver.calls  # the demo's option reached it


def test_unknown_demo_names_the_choices():
    with pytest.raises(ValueError, match="proteins, microbe, taxon"):
        find_demo("nope")


def test_demo_queries_become_browser_examples():
    card = find_demo("proteins").example()
    assert card["ids"] == "TP53\nNOTAGENE"
    assert card["params"] == {"resolve_protein": {"organism": "9606"}}
    assert find_demo("proteins").get_kwargs()["organism"] == "9606"
    assert {d.name for d in DEMOS} == {"proteins", "microbe", "taxon"}


def test_landing_page_takes_examples_and_a_notice(recording_registry):
    registry, _ = recording_registry
    page = render_lookup_page(registry, examples=[TOY.example()], notice="Demo <mode>")
    assert 'class="notice"' in page and "Demo &lt;mode&gt;" in page
    assert "Symbols of a gene" in page
    assert "Structures and pathways for cancer genes" not in page  # built-ins replaced
    assert 'class="notice"' not in render_lookup_page(registry)


def test_app_with_a_registry_never_discovers(monkeypatch, recording_registry):
    testclient = pytest.importorskip("fastapi.testclient")
    registry, _ = recording_registry

    def refuse():
        raise AssertionError("the demo app must not discover installed sources")

    monkeypatch.setattr(serve, "discover_registry", refuse)
    monkeypatch.setattr("weaverkit.view.discover_registry", refuse)
    client = testclient.TestClient(
        serve.create_app(registry=registry, examples=[TOY.example()], notice=NOTICE)
    )
    assert NOTICE in client.get("/").text
    assert NOTICE in client.get("/explore").text
    body = {"batch": {"format": "lines", "input_type": QUERY, "text": "TP53"}, "want": [SYMBOL]}
    payload = client.post("/api/run", json=body).json()
    assert payload["ok"] and payload["table"]["rows"][0][SYMBOL] == "child"
    assert client.post("/api/plan", json={"from_types": [QUERY], "to_types": [GENE]}).json()


def test_build_data_uses_a_given_registry(monkeypatch, recording_registry):
    registry, _ = recording_registry
    monkeypatch.setattr(
        "weaverkit.view.discover_registry", lambda: pytest.fail("no discovery expected")
    )
    data = build_data(registry=registry)
    assert data["meta"]["problems"] == []
    assert data["network"]
