"""The form-first landing page (3.3) and the Result table the browser receives."""

from __future__ import annotations

import asyncio
import json

import braidworks as bw
import pytest
from braidworks.core.catalog import field_catalog
from test_serve_parameters import QUERY, SYMBOL, client_for
from test_serve_parameters import recording_registry as _recording_fixture
from weaverkit._lookup_ui import page_data, render_lookup_page

from weaverkit import serve

recording_registry = _recording_fixture


def _injected(page: str, name: str):
    start = page.index(f"const {name} = ") + len(f"const {name} = ")
    return json.loads(page[start : page.index(";\n", start)].replace("<\\/", "</"))


def test_page_injects_the_installed_catalogue_and_start_types(recording_registry):
    registry, _ = recording_registry
    page = render_lookup_page(registry)
    catalog = _injected(page, "CATALOG")
    assert {row[0] for row in catalog} == set(field_catalog(registry))
    assert _injected(page, "STARTS") == [QUERY]  # consumed, produced by nothing


def test_start_types_are_inputs_nothing_produces(recording_registry):
    registry, _ = recording_registry
    rows, starts = page_data(registry)
    produced = {row[0] for row in rows if row[3]}
    assert starts and not set(starts) & produced
    consumers = {row[0]: row[4] for row in rows}
    assert [consumers[t] for t in starts] == sorted((consumers[t] for t in starts), reverse=True)


def test_injected_json_cannot_close_the_script(monkeypatch, recording_registry):
    registry, _ = recording_registry
    import weaverkit._lookup_ui as ui

    monkeypatch.setattr(ui, "page_data", lambda reg: ([["x</script>", "", [], [], 0]], []))
    page = render_lookup_page(registry)
    assert "x</script>" not in page and "x<\\/script>" in page


def test_landing_page_is_the_form_not_the_graph_or_advanced_settings(recording_registry):
    registry, _ = recording_registry
    page = render_lookup_page(registry)
    for element in ('id="ids"', 'id="types"', 'id="q"', 'id="run"', 'href="/explore"'):
        assert element in page, element
    # settings, not the per-candidate confidence a review row shows
    for advanced in (
        'id="builder"',
        "review_policy",
        "lease",
        "confidence_threshold",
        "max_expansion",
    ):
        assert advanced not in page, advanced


def test_app_serves_the_form_at_root_and_the_graph_at_explore(
    monkeypatch, recording_registry, tmp_path
):
    registry, _ = recording_registry
    client = client_for(monkeypatch, registry, data_dir=tmp_path)
    assert 'id="ids"' in client.get("/").text
    explore = client.get("/explore")
    assert explore.status_code == 200 and 'id="builder"' in explore.text


# --- the table the page renders is Python's Result -----------------------------------


@pytest.fixture
def python_result(recording_registry):
    registry, _ = recording_registry
    with bw.Session(registry=registry) as session:
        return session.get(["TP53", "BRCA1"], have=QUERY, want=[SYMBOL])


def _batch_payload(registry):
    batch = {"text": "TP53\nBRCA1", "format": "lines", "input_type": QUERY}
    return asyncio.run(serve.execute_query_response(registry, {}, [SYMBOL], [], batch))


def test_run_payload_carries_result_rows(recording_registry, python_result):
    registry, _ = recording_registry
    table = _batch_payload(registry)["table"]
    assert table["rows"] == json.loads(json.dumps(python_result.to_json()["rows"]))
    assert table["summary"] == python_result.summary()
    assert table["columns"] == python_result.columns
    assert table["want"] == [SYMBOL]


def test_run_payload_exports_are_python_exports(recording_registry, python_result):
    registry, _ = recording_registry
    exports = _batch_payload(registry)["exports"]
    assert exports["csv"] == python_result.to_csv()
    assert exports["tsv"] == python_result.to_csv(sep="\t")
    assert (
        json.loads(exports["json"])["rows"]
        == json.loads(json.dumps(python_result.to_json()))["rows"]
    )


def test_list_sizes_travel_beside_plain_json_lists(recording_registry):
    registry, _ = recording_registry
    payload = asyncio.run(
        serve.execute_query_response(registry, {QUERY: "TP53"}, ["go.biological_process"], [], None)
    )
    table = payload["table"]
    for row, sizes in zip(table["rows"], table["sizes"], strict=True):
        for field, size in sizes.items():
            assert isinstance(row[field], list) and size["shown"] == len(row[field])
            assert size["complete"] == (size["total"] == size["shown"])
