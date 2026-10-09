"""Progress follows actual fetch/build work and cache reuse stays silent."""

from disbiome_weaver import fixture, setup
from disbiome_weaver.factory import build_disbiome_weaver


def test_configured_progress_is_forwarded_and_reports_actual_phases(tmp_path, monkeypatch):
    tables = {
        "experiment": fixture._EXPERIMENTS,
        "disease": fixture._DISEASES,
        "organism": fixture._ORGANISMS,
        "publication": fixture._PUBLICATIONS,
    }
    monkeypatch.setattr(setup, "_fetch", tables.__getitem__)
    events = []
    callback = lambda *event: events.append(event)
    path = tmp_path / "source.sqlite"
    weaver = build_disbiome_weaver(db_path=path, auto_setup=True, progress=callback)
    assert weaver._backends["local"].is_configured()
    assert [(event[1], event[4]) for event in events if event[0] == "fetch"] == [
        (name, finished)
        for name in ["experiment", "disease", "organism", "publication"]
        for finished in [False, True]
    ]
    assert events[0][0] == events[-1][0] == "build" and events[-1][-1]
    events.clear()
    build_disbiome_weaver(db_path=path, progress=callback)
    assert events == []
