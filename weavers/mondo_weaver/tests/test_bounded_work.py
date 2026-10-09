"""One graph traversal per resolved term, and none for identity-only lookup."""

from contextlib import contextmanager

from mondo_weaver.backends.local import ANCESTORS, DEPTH, MondoLocalBackend
from mondo_weaver.fixture import _term
from mondo_weaver.setup import write_db


async def test_group_gating_and_shared_dag_traversal(tmp_path, monkeypatch):
    path = tmp_path / "dag.sqlite"
    write_db(
        path,
        data_version="fixture",
        terms=[
            _term("MONDO:1", "root"),
            _term("MONDO:2", "parent", parents=["MONDO:1"]),
            _term(
                "MONDO:3",
                "leaf",
                parents=["MONDO:1", "MONDO:2"],
                xrefs=[("MESH", "D1", True), ("MESH", "D2", True)],
            ),
        ],
    )
    backend = MondoLocalBackend(path)
    statements = []
    session = backend._source.session

    @contextmanager
    def traced():
        with session() as con:
            con.set_trace_callback(statements.append)
            yield con

    monkeypatch.setattr(backend._source, "session", traced)
    queries = [{"disease.mesh.id": value} for value in ("D1", "D2", "D1")]
    kwargs = {"requested_outputs": frozenset()}
    records = await backend.fetch(
        "mondo.lookup_by_mesh", queries, groups_to_compute=frozenset({"identity"}), **kwargs
    )
    assert all(record.found for record in records)
    assert not any("WITH RECURSIVE" in sql for sql in statements)
    statements.clear()
    records = await backend.fetch(
        "mondo.lookup_by_mesh",
        queries,
        groups_to_compute=frozenset({"identity", "term", "ancestors"}),
        **kwargs,
    )
    assert sum("WITH RECURSIVE" in sql for sql in statements) == 1
    assert records[0].values[DEPTH] == 1  # shortest route across competing DAG paths
    assert len(records[0].values[ANCESTORS]) == 3
    records[0].values[ANCESTORS].clear()
    assert records[1].values[ANCESTORS] and records[2].values[ANCESTORS]
