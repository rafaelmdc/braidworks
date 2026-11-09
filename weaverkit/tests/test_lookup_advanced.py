"""Advanced settings (collapsed) and the examples gallery (3.6)."""

from __future__ import annotations

import json

from braidworks.core.catalog import field_catalog
from braidworks.core.run_store import SQLiteRunStore
from test_lookup_results import reviewing as _reviewing_fixture
from test_serve_parameters import QUERY, SYMBOL, client_for
from test_serve_parameters import recording_registry as _recording_fixture
from weaverkit._lookup_ui import EXAMPLES, render_lookup_page, runnable_examples

recording_registry = _recording_fixture
reviewing = _reviewing_fixture


def _injected(page: str, name: str):
    start = page.index(f"const {name} = ") + len(f"const {name} = ")
    return json.loads(page[start : page.index(";\n", start)].replace("<\\/", "</"))


def test_examples_are_offered_only_when_the_install_can_answer_them(recording_registry):
    registry, _ = recording_registry
    catalog = field_catalog(registry)
    assert runnable_examples(catalog) == []  # the fixture has no proteins or organisms
    assert _injected(render_lookup_page(registry), "EXAMPLES") == []


def test_an_answerable_example_is_offered(monkeypatch, recording_registry):
    registry, _ = recording_registry
    import weaverkit._lookup_ui as ui

    mine = {"name": "Symbols", "have": QUERY, "ids": "TP53", "want": [SYMBOL], "params": {}}
    unreachable = {**mine, "name": "Nope", "want": ["not.a.field"]}
    monkeypatch.setattr(ui, "EXAMPLES", [mine, unreachable])
    assert _injected(render_lookup_page(registry), "EXAMPLES") == [mine]


def test_built_in_examples_name_real_fields():
    for example in EXAMPLES:
        assert example["name"] and example["ids"].strip() and example["want"], example
        assert set(example) == {"name", "have", "ids", "want", "params"}


def test_page_shares_recipes_with_the_explore_builder(recording_registry):
    registry, _ = recording_registry
    page = render_lookup_page(registry)
    assert 'const RECIPES_KEY = "braidworks.recipes"' in page
    from weaverkit._serve_ui import SERVE_JS

    assert 'const RECIPES_KEY = "braidworks.recipes"' in SERVE_JS


def test_advanced_settings_reach_the_run(monkeypatch, recording_registry, tmp_path):
    """The body the page sends with Advanced settings: policies, expansion and a saved run."""
    registry, _ = recording_registry
    client = client_for(monkeypatch, registry, data_dir=tmp_path)
    body = {
        "have": {},
        "want": [SYMBOL],
        "batch": {"text": "TP53", "format": "lines", "input_type": QUERY},
        "params": {},
        "policy": "local_only",
        "review_policy": "allow_continue",
        "confidence_threshold": 0.5,
        "expand": "top_k",
        "k": 2,
        "max_expansion": 50,
        "persistence": {
            "version": 1,
            "cache_db": "data/cache.sqlite",
            "run_db": "data/runs.sqlite",
            "run_id": "mine",
            "lease_seconds": 30,
        },
    }
    payload = client.post("/api/run", json=body).json()
    assert payload["ok"], payload
    assert payload["review_policy"] == "allow_continue"
    assert payload["confidence_threshold"] == 0.5
    assert payload["run"]["run_id"] == "mine"
    assert (tmp_path / "data" / "cache.sqlite").exists()
    assert [cp.run_id for cp in SQLiteRunStore(str(tmp_path / "data" / "runs.sqlite")).list()] == [
        "mine"
    ]


def test_saved_run_reviews_resume_from_the_store(monkeypatch, reviewing, tmp_path):
    client = client_for(monkeypatch, reviewing, data_dir=tmp_path)
    persistence = {"version": 1, "run_db": "runs.sqlite", "run_id": "r1"}
    body = {
        "want": [SYMBOL],
        "batch": {"text": "TP53", "format": "lines", "input_type": QUERY},
        "persistence": persistence,
    }
    paused = client.post("/api/run", json=body).json()
    assert paused["run"]["status"] == "review" and "review_token" not in paused
    key = paused["table"]["review"][0]["key"]
    resumed = client.post(
        "/api/resume",
        json={
            "run_id": "r1",
            "persistence": persistence,
            "decisions": [
                {"version": 1, "entity_key": key, "action": "select", "candidate_index": 0}
            ],
        },
    ).json()
    assert resumed["ok"] and resumed["run"]["status"] == "complete"
    assert resumed["table"]["rows"][0]["status"] == "resolved"
