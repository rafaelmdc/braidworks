"""Runtime traversal must terminate even when stored graph data was corrupted."""

import sqlite3

import pytest
from mondo_weaver.backends.local import MondoLocalBackend
from mondo_weaver.fixture import _term
from mondo_weaver.setup import write_db


@pytest.mark.parametrize("defect", ["cycle", "dangling"])
def test_corrupted_graph_returns_error_without_recursive_depth_explosion(tmp_path, defect):
    path = tmp_path / "graph.sqlite"
    write_db(
        path,
        data_version="test",
        terms=[
            _term("MONDO:1", "root"),
            _term("MONDO:2", "child", parents=["MONDO:1"], xrefs=[("MESH", "D1", True)]),
        ],
    )
    backend = MondoLocalBackend(path)
    with sqlite3.connect(path) as con:
        con.execute(
            "INSERT INTO isa VALUES (?, ?)",
            ("MONDO:1", "MONDO:2" if defect == "cycle" else "MONDO:9"),
        )
        # Guard the regression itself against an accidentally restored infinite CTE.
        ticks = 0

        def bounded():
            nonlocal ticks
            ticks += 1
            return int(ticks > 100)

        con.set_progress_handler(bounded, 100)
        record = backend._lookup_one(
            con,
            {"disease.mesh.id": "D1"},
            "disease.mesh.id",
            "MESH",
            frozenset({"term", "ancestors"}),
            {},
        )
    expected = "cycle" if defect == "cycle" else "missing"
    assert record.error and expected in record.error
    assert not record.found and not record.values
