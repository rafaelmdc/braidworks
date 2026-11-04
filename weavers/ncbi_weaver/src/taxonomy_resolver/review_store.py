"""Source-local reviewed history, independent of replaceable taxonomy artifacts."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from braidworks.core.sqlite import readonly_uri

from .db import SCHEMA_STATEMENTS, DatabaseHandle, _scope

_COLUMNS = (
    "original_name",
    "normalized_name",
    "provided_level",
    "resolved_taxid",
    "matched_scientific_name",
    "match_type",
    "status",
    "score",
    "decision_action",
    "taxonomy_build_version",
    "reviewer",
    "warnings_json",
    "notes",
    "created_at",
)


def default_review_path(taxonomy_path: str | Path) -> Path:
    path = Path(taxonomy_path)
    return path.with_name(path.name + ".reviews.sqlite")


def initialize_review_store(database: DatabaseHandle, *, create_indexes: bool = True) -> None:
    with _scope(database, write=True) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS review_schema (version INTEGER NOT NULL)")
        versions = connection.execute("SELECT version FROM review_schema").fetchall()
        if versions and (len(versions) != 1 or versions[0][0] != 1):
            raise ValueError("Unsupported review schema version")
        if not versions:
            connection.execute("INSERT INTO review_schema VALUES (1)")
        connection.execute(SCHEMA_STATEMENTS[3])
        if create_indexes:
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_reviewed_mappings_norm_level "
                "ON reviewed_mappings(normalized_name, provided_level)"
            )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS imported_review_rows (digest TEXT PRIMARY KEY)"
        )


def migrate_review_history(source: str | Path, destination: str | Path) -> int:
    """Copy legacy rows atomically/idempotently, never modifying the original.

    Each full row's digest makes repeated imports harmless. A failure rolls back
    both history insertion and import markers; caller can retry or use the old path.
    """
    source, destination = Path(source), Path(destination)
    if source.absolute() == destination.absolute():
        return 0
    initialize_review_store(destination)
    with closing(sqlite3.connect(readonly_uri(source), uri=True)) as reader:
        exists = reader.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reviewed_mappings'"
        ).fetchone()
        if not exists:
            return 0
        rows = reader.execute(
            "SELECT id," + ",".join(_COLUMNS) + " FROM reviewed_mappings ORDER BY id"
        ).fetchall()
    count = 0
    with _scope(destination, write=True) as writer:
        for imported_row in rows:
            row = imported_row[1:]
            digest = hashlib.sha256(
                json.dumps(imported_row, separators=(",", ":"), ensure_ascii=False).encode()
            ).hexdigest()
            cursor = writer.execute(
                "INSERT OR IGNORE INTO imported_review_rows VALUES (?)", (digest,)
            )
            if cursor.rowcount:
                writer.execute(
                    "INSERT INTO reviewed_mappings ("
                    + ",".join(_COLUMNS)
                    + ") VALUES ("
                    + ",".join("?" for _ in _COLUMNS)
                    + ")",
                    row,
                )
                count += 1
    return count


class ReviewedDecisionRepository:
    """Own the reviewed-decision handle; reuse existing conservative cache rules."""

    def __init__(self, path: str | Path) -> None:
        initialize_review_store(path)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def lookup(self, request, taxonomy_build_version):
        from .cache import lookup_reviewed_mapping

        return lookup_reviewed_mapping(
            request,
            taxonomy_db_path=self.connection,
            cache_db_path=self.connection,
            taxonomy_build_version=taxonomy_build_version,
        )

    def record(self, decision):
        from .cache import record_reviewed_mapping

        record_reviewed_mapping(
            decision, taxonomy_db_path=self.connection, cache_db_path=self.connection
        )
