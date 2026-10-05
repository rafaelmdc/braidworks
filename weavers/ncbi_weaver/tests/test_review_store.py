import sqlite3

import pytest
from taxonomy_resolver import db
from taxonomy_resolver.review_store import (
    default_review_path,
    initialize_review_store,
    migrate_review_history,
)
from taxonomy_resolver.schemas import ResolveRequest
from taxonomy_resolver.service import TaxonomyResolverService


def _row(name):
    return (
        name,
        name,
        None,
        1,
        "root",
        "exact_scientific",
        "confirmed_by_user",
        1.0,
        "confirm",
        "build",
        "tester",
        "[]",
        None,
        "2026-01-01",
    )


def test_idempotent_migration_preserves_original_and_duplicates(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "reviews"
    db.initialize_database(source)
    db.insert_reviewed_mapping(source, _row("first"))
    db.insert_reviewed_mapping(source, _row("first"))
    before = source.read_bytes()
    assert migrate_review_history(source, destination) == 2
    assert migrate_review_history(source, destination) == 0
    assert source.read_bytes() == before
    with db._scope(destination) as connection:
        assert connection.execute("SELECT COUNT(*) FROM reviewed_mappings").fetchone()[0] == 2
        assert (
            connection.execute("SELECT name FROM sqlite_master WHERE name='taxa'").fetchone()
            is None
        )


def test_failed_migration_rolls_back_rows_and_markers(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "reviews"
    db.initialize_database(source)
    for name in ("first", "second"):
        db.insert_reviewed_mapping(source, _row(name))
    initialize_review_store(destination)
    with db._scope(destination, write=True) as connection:
        connection.execute(
            "CREATE TRIGGER reject_second BEFORE INSERT ON reviewed_mappings "
            "WHEN NEW.original_name='second' BEGIN SELECT RAISE(ABORT, 'stop'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="stop"):
        migrate_review_history(source, destination)
    with db._scope(destination, write=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM reviewed_mappings").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM imported_review_rows").fetchone()[0] == 0
        connection.execute("DROP TRIGGER reject_second")
    assert migrate_review_history(source, destination) == 2


def test_refresh_keeps_separate_history_and_readonly_reference(tmp_path):
    source = tmp_path / "taxonomy"
    db.initialize_database(source)
    db.upsert_metadata(source, {"taxonomy_build_version": "build"})
    db.insert_reviewed_mapping(source, _row("first"))
    with TaxonomyResolverService(source) as service:
        assert service.cache_db_path == default_review_path(source)
        with pytest.raises(sqlite3.OperationalError):
            service._taxonomy_connection.execute("DELETE FROM metadata")
    replacement = tmp_path / "new"
    db.initialize_database(replacement)
    db.upsert_metadata(replacement, {"taxonomy_build_version": "new-build"})
    replacement.replace(source)
    with TaxonomyResolverService(source) as service:
        assert (
            service._cache_connection.execute("SELECT COUNT(*) FROM reviewed_mappings").fetchone()[
                0
            ]
            == 1
        )
        # Existing conservative matching refuses history from another reference build.
        assert service._reviews.lookup(ResolveRequest(original_name="first"), "new-build") is None


def test_borrowed_reference_survives_service_close(tmp_path):
    source = tmp_path / "taxonomy"
    db.initialize_database(source)
    connection = db.connect(source)
    try:
        with TaxonomyResolverService(source, taxonomy_connection=connection):
            pass
        assert connection.execute("SELECT COUNT(*) FROM taxa").fetchone()[0] == 0
    finally:
        connection.close()


async def test_backend_rejects_replaced_reference_and_closes_batches(tmp_path):
    from braidworks.core.exceptions import BackendConfigurationError
    from ncbi_weaver import vocab
    from ncbi_weaver.backends.local import LocalTaxonomyBackend
    from ncbi_weaver.fixture import build_fixture_db

    source = build_fixture_db(tmp_path)
    backend = LocalTaxonomyBackend(source)
    first = backend.fingerprint()
    result = await backend.resolve(vocab.DESCRIBE_TAXON, ["853", "853"], need_lineage=False)
    assert len(result) == 2
    assert backend.fingerprint() == first  # Creating review history never changes source.
    directory = tmp_path / "new"
    directory.mkdir()
    replacement = build_fixture_db(directory)
    replacement.replace(source)
    with pytest.raises(BackendConfigurationError, match="reopen"):
        await backend.resolve(vocab.DESCRIBE_TAXON, ["853"], need_lineage=False)
    fresh = LocalTaxonomyBackend(source)
    assert fresh.fingerprint() != first
