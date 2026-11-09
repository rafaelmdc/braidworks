"""Browser fixes from the newcomer walkthrough: row labels and field descriptions."""

from test_serve_parameters import QUERY, SYMBOL, client_for
from test_serve_parameters import recording_registry as _recording_fixture
from weaverkit.keys import SHARED_KEYS
from weaverkit.view import _classify

recording_registry = _recording_fixture


def test_table_batches_label_rows_by_their_values(monkeypatch, recording_registry, tmp_path):
    registry, _ = recording_registry
    client = client_for(monkeypatch, registry, data_dir=tmp_path)
    body = {"batch": {"format": "csv", "text": f"{QUERY}\nTP53\nBRCA1\n"}, "want": [SYMBOL]}
    payload = client.post("/api/run", json=body).json()
    assert payload["ok"], payload
    assert [row["input"] for row in payload["table"]["rows"]] == ["TP53", "BRCA1"]


def test_entry_fields_keep_their_own_description():
    role, description = _classify("protein.query")
    assert role == "entry"
    assert description == SHARED_KEYS["protein.query"]  # what field search shows
    assert "organism" not in description


def test_a_single_have_input_is_labelled_by_its_value(monkeypatch, recording_registry, tmp_path):
    registry, _ = recording_registry
    client = client_for(monkeypatch, registry, data_dir=tmp_path)
    payload = client.post("/api/run", json={"have": {QUERY: "TP53"}, "want": [SYMBOL]}).json()
    assert payload["ok"], payload
    assert payload["table"]["rows"][0]["input"] == "TP53"
