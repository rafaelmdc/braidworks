"""The browser's Python export is bw.get code that reproduces the browser's own table."""

import runpy

import braidworks._session
import pytest
from test_serve_parameters import GENE, QUERY, SYMBOL, client_for
from test_serve_parameters import recording_registry as _recording_fixture

from weaverkit import serve

recording_registry = _recording_fixture

BATCHES = {
    "typed ids": {"format": "lines", "input_type": QUERY, "text": "TP53\nBRCA1"},
    "mixed table": {"format": "csv", "text": f"{QUERY},{GENE}\nTP53,\n,7157\n"},
}


@pytest.mark.parametrize("batch", BATCHES.values(), ids=BATCHES.keys())
def test_generated_script_writes_the_browsers_csv(monkeypatch, recording_registry, tmp_path, batch):
    registry, _ = recording_registry
    params = {"resolve": {"organism": "9606"}}
    client = client_for(monkeypatch, registry, data_dir=tmp_path)
    browser = client.post("/api/run", json={"batch": batch, "want": [SYMBOL], "params": params})
    browser_csv = browser.json()["exports"]["csv"]

    document = serve.batch_code_response(registry, {}, [SYMBOL], [], batch, params=params)
    code = document["artifacts"]["python"]
    assert code.startswith("import braidworks as bw\n")
    assert "params={'resolve': {'organism': '9606'}}" in code
    assert "braidworks.core" not in code  # the public API only

    monkeypatch.setattr(
        braidworks._session, "build_registry_from_entry_points", lambda only=None: registry
    )
    monkeypatch.chdir(tmp_path)
    (tmp_path / "generated.py").write_text(code)
    runpy.run_path(str(tmp_path / "generated.py"))
    assert (tmp_path / "braidworks-results.csv").read_text() == browser_csv


def test_typed_ids_use_have_and_mixed_rows_name_their_fields(recording_registry):
    registry, _ = recording_registry
    typed = serve.batch_code_response(registry, {}, [SYMBOL], [], BATCHES["typed ids"])
    assert f"['TP53', 'BRCA1'],\n        have='{QUERY}'," in typed["artifacts"]["python"]
    mixed = serve.batch_code_response(registry, {}, [SYMBOL], [], BATCHES["mixed table"])
    assert f"[{{'{QUERY}': 'TP53'}}, {{'{GENE}': 7157}}]," in mixed["artifacts"]["python"]
    assert "have=" not in mixed["artifacts"]["python"]


def test_settings_left_at_their_defaults_are_not_written(recording_registry):
    registry, _ = recording_registry
    code = serve.code_response(registry, {QUERY: "TP53"}, [SYMBOL], [])["artifacts"]["python"]
    assert "with bw.Session() as s:" in code
    for default in ("backend=", "review=", "min_confidence=", "max_expansion=", "expand="):
        assert default not in code, default
