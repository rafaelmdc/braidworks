import sqlite3

import pytest
from braidworks.core.sqlite import connection_scope, transaction


def test_owned_closes_on_exception(tmp_path):
    with pytest.raises(RuntimeError), connection_scope(tmp_path / "owned.sqlite") as connection:
        raise RuntimeError("stop")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_borrowed_survives_and_preserves_transaction():
    with connection_scope(":memory:") as connection:
        connection.execute("CREATE TABLE example (value)")
        connection.execute("INSERT INTO example VALUES (1)")
        with connection_scope(connection):
            assert connection.in_transaction
        with pytest.raises(ValueError, match="already active"), transaction(connection):
            pass
        assert connection.in_transaction
        connection.rollback()
        assert connection.execute("SELECT COUNT(*) FROM example").fetchone()[0] == 0


def test_transaction_rolls_back_and_commits(tmp_path):
    with connection_scope(tmp_path / "db") as connection:
        connection.execute("CREATE TABLE example (value)")
        with pytest.raises(RuntimeError), transaction(connection):
            connection.execute("INSERT INTO example VALUES (1)")
            raise RuntimeError("stop")
        assert connection.execute("SELECT COUNT(*) FROM example").fetchone()[0] == 0
        with transaction(connection):
            connection.execute("INSERT INTO example VALUES (2)")
        assert not connection.in_transaction
        assert connection.execute("SELECT value FROM example").fetchone()[0] == 2


def test_readonly_special_characters_and_missing_path(tmp_path):
    path = tmp_path / "spaces ? # %.sqlite"
    with connection_scope(path) as connection:
        connection.execute("CREATE TABLE example (value)")
    with connection_scope(path, readonly=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM example").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO example VALUES (1)")
    missing = tmp_path / "missing"
    with pytest.raises(sqlite3.OperationalError), connection_scope(missing, readonly=True):
        pass
    assert not missing.exists()
