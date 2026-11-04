import sqlite3

import pytest
from taxonomy_resolver import db
from taxonomy_resolver.cache import _ensure_cache_database


def test_borrowed_transaction_is_not_committed_or_rolled_back(tmp_path):
    path = tmp_path / "db"
    db.initialize_database(path)
    connection = db.connect(path)
    try:
        connection.execute("INSERT INTO metadata VALUES ('caller', 'pending')")
        db.upsert_metadata(connection, {"helper": "pending"})
        assert db.fetch_all_metadata(connection) == {"caller": "pending", "helper": "pending"}
        with pytest.raises(sqlite3.IntegrityError):
            db.insert_taxon_name_rows([(None, None, None, None, None)], connection)
        assert connection.in_transaction
        assert db.fetch_all_metadata(path) == {}
        connection.rollback()
        assert db.fetch_all_metadata(connection) == {}
    finally:
        connection.close()


def test_replaced_database_is_initialized(tmp_path):
    path = tmp_path / "db"
    _ensure_cache_database(path, create_indexes=True)
    path.unlink()
    _ensure_cache_database(path, create_indexes=True)
    with db._scope(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM reviewed_mappings").fetchone()[0] == 0


def test_future_schema_is_rejected(tmp_path):
    path = tmp_path / "db"
    db.initialize_database(path)
    with db._scope(path, write=True) as connection:
        connection.execute("UPDATE taxonomy_schema SET version = 99")
    with pytest.raises(ValueError, match="schema version: 99"):
        db.initialize_database(path)


def test_reads_do_not_create_and_paths_do_not_mutate_legacy_default(tmp_path):
    legacy = tmp_path / "legacy"
    db.initialize_database(legacy)
    connection = db.connect(legacy)
    connection.close()
    path = tmp_path / "other ? # db"
    db.initialize_database(path)
    db.upsert_metadata(path, {"test": "value"})
    assert db.fetch_all_metadata(path) == {"test": "value"}
    assert db.get_default_db_path() == legacy
    db.insert_taxa_rows([])  # Legacy no-path wrapper uses the explicit connect() default.


def test_missing_read_does_not_create_database(tmp_path):
    path = tmp_path / "missing"
    with pytest.raises(sqlite3.OperationalError):
        db.fetch_all_metadata(path)
    assert not path.exists()


def test_deferred_commit_requires_borrowed_handle(tmp_path):
    path = tmp_path / "db"
    db.initialize_database(path)
    with pytest.raises(ValueError, match="caller-owned"):
        db.upsert_metadata(path, {"lost": "value"}, commit=False)
    connection = db.connect(path)
    try:
        db.upsert_metadata(connection, {"pending": "value"}, commit=False)
        assert connection.in_transaction
        assert db.fetch_all_metadata(path) == {}
        connection.commit()
        assert db.fetch_all_metadata(path) == {"pending": "value"}
    finally:
        connection.close()
