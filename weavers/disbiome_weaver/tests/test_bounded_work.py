"""Light groups avoid parsing full records and repeat queries share only batch work."""

from contextlib import contextmanager

from disbiome_weaver.backends import local
from disbiome_weaver.fixture import fixture_db_path


async def test_summary_and_compact_groups_do_not_read_json(monkeypatch):
    backend = local.DisbiomeLocalBackend(fixture_db_path())
    statements = []
    session = backend._source.session

    @contextmanager
    def traced():
        with session() as con:
            con.set_trace_callback(statements.append)
            yield con

    monkeypatch.setattr(backend._source, "session", traced)
    for group in ("summary", "associations"):
        records = await backend.fetch(
            "disbiome.list_diseases",
            [{"ncbi.taxon.species_id": taxid} for taxid in (1591, "1591")],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({group}),
        )
        assert all(record.found for record in records)
        assert records[0].query != records[1].query
        if group == "associations":
            records[0].values[local.ASSOCIATIONS].clear()
            assert records[1].values[local.ASSOCIATIONS]
    data_queries = [sql for sql in statements if "FROM association" in sql]
    assert len(data_queries) == 2
    assert all("full_json" not in sql for sql in data_queries)


async def test_compact_projection_preserves_source_scalar_types(tmp_path):
    import sqlite3

    from disbiome_weaver.setup import db_is_valid, write_db

    path = tmp_path / "fixture.sqlite"
    write_db(
        path,
        experiments=[
            {
                "experiment_id": 1,
                "organism_ncbi_id": 1,
                "disease_name": "fixture",
                "meddra_id": 123,
                "method_name": "None",
            }
        ],
        diseases=[],
        organisms=[],
        publications=[],
    )
    backend = local.DisbiomeLocalBackend(path)
    kwargs = {"requested_outputs": frozenset()}
    compact = (
        await backend.fetch(
            "disbiome.list_diseases",
            [{"ncbi.taxon.species_id": 1}],
            groups_to_compute=frozenset({"associations"}),
            **kwargs,
        )
    )[0]
    full = (
        await backend.fetch(
            "disbiome.list_diseases",
            [{"ncbi.taxon.species_id": 1}],
            groups_to_compute=frozenset({"full", "associations"}),
            **kwargs,
        )
    )[0]
    assert compact.values[local.ASSOCIATIONS] == full.values[local.ASSOCIATIONS]
    assert compact.values[local.ASSOCIATIONS][0]["meddra_id"] == 123
    with sqlite3.connect(path) as con:
        con.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
    assert not db_is_valid(path)
    assert not local.DisbiomeLocalBackend(path).is_configured()
