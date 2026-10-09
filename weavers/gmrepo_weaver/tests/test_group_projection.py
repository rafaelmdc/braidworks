"""Summary SQL avoids projecting association measurements without losing counts."""

from contextlib import contextmanager

from gmrepo_weaver.backends.local import GmrepoLocalBackend
from gmrepo_weaver.fixture import fixture_db_path


async def test_summary_gates_association_projection(monkeypatch):
    backend = GmrepoLocalBackend(fixture_db_path())
    statements = []
    session = backend._source.session

    @contextmanager
    def traced():
        with session() as connection:
            connection.set_trace_callback(statements.append)
            yield connection

    monkeypatch.setattr(backend._source, "session", traced)
    query = [{"ncbi.taxon.id": 816}]
    kwargs = {"requested_outputs": frozenset()}
    summary = (
        await backend.fetch(
            "gmrepo.list_abundances", query, groups_to_compute=frozenset({"summary"}), **kwargs
        )
    )[0]
    data_queries = [sql for sql in statements if "FROM association" in sql]
    assert data_queries and all("abundance_mean" not in sql for sql in data_queries)
    assert "microbe.abundance.records" not in summary.values
    full = (
        await backend.fetch(
            "gmrepo.list_abundances",
            query,
            groups_to_compute=frozenset({"summary", "full"}),
            **kwargs,
        )
    )[0]
    for key, value in summary.values.items():
        assert full.values[key] == value
    assert full.values["microbe.abundance.records"]["associations"]
