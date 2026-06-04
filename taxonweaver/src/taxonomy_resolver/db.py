"""SQLite access layer for taxonomy reference and cache state.

The resolver should keep SQL localized here so service and policy code remain
readable and testable.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH: Path | None = None
DatabaseHandle = sqlite3.Connection | Path | str | None

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS taxa (
        taxid INTEGER PRIMARY KEY,
        parent_taxid INTEGER NOT NULL,
        rank TEXT NOT NULL,
        is_root INTEGER NOT NULL DEFAULT 0,
        source_node_embl_code TEXT,
        division_id INTEGER,
        inherited_div_flag INTEGER,
        genetic_code_id INTEGER,
        inherited_gc_flag INTEGER,
        mitochondrial_genetic_code_id INTEGER,
        inherited_mgc_flag INTEGER,
        genbank_hidden_flag INTEGER,
        hidden_subtree_root_flag INTEGER,
        comments TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS taxon_names (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        taxid INTEGER NOT NULL,
        name_txt TEXT NOT NULL,
        unique_name TEXT,
        name_class TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        FOREIGN KEY (taxid) REFERENCES taxa(taxid)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lineage_cache (
        taxid INTEGER PRIMARY KEY,
        lineage_json TEXT NOT NULL,
        FOREIGN KEY (taxid) REFERENCES taxa(taxid)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reviewed_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        provided_level TEXT,
        resolved_taxid INTEGER,
        matched_scientific_name TEXT,
        match_type TEXT NOT NULL,
        status TEXT NOT NULL,
        score REAL,
        decision_action TEXT NOT NULL,
        taxonomy_build_version TEXT NOT NULL,
        reviewer TEXT,
        warnings_json TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL
    )
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_taxa_parent_taxid ON taxa(parent_taxid)",
    "CREATE INDEX IF NOT EXISTS idx_taxon_names_taxid ON taxon_names(taxid)",
    "CREATE INDEX IF NOT EXISTS idx_taxon_names_name_txt ON taxon_names(name_txt)",
    "CREATE INDEX IF NOT EXISTS idx_taxon_names_normalized_name ON taxon_names(normalized_name)",
    "CREATE INDEX IF NOT EXISTS idx_taxon_names_name_class ON taxon_names(name_class)",
    "CREATE INDEX IF NOT EXISTS idx_taxon_names_name_txt_class_taxid ON taxon_names(name_txt, name_class, taxid)",
    "CREATE INDEX IF NOT EXISTS idx_taxon_names_taxid_class_name_txt ON taxon_names(taxid, name_class, name_txt)",
    "CREATE INDEX IF NOT EXISTS idx_reviewed_mappings_norm_level ON reviewed_mappings(normalized_name, provided_level)",
]


def connect(db_path: DatabaseHandle = None) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""

    global DEFAULT_DB_PATH
    if isinstance(db_path, sqlite3.Connection):
        return db_path
    resolved_path = Path(db_path) if db_path is not None else get_default_db_path()
    connection = sqlite3.connect(resolved_path)
    connection.row_factory = sqlite3.Row
    DEFAULT_DB_PATH = resolved_path
    return connection


def get_default_db_path() -> Path:
    """Return the last database path used by the current process."""

    if DEFAULT_DB_PATH is None:
        raise RuntimeError("No default database path is set for the current process.")
    return DEFAULT_DB_PATH


def initialize_database(db_path: DatabaseHandle, *, create_indexes: bool = True) -> None:
    """Create the reference and cache schema in a new or existing database."""

    with connect(db_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        if create_indexes:
            for statement in INDEX_STATEMENTS:
                connection.execute(statement)
        connection.commit()


def clear_reference_tables(db_path: DatabaseHandle, *, commit: bool = True) -> None:
    """Remove reference-build data while preserving reviewed mapping history."""

    with connect(db_path) as connection:
        connection.execute("DELETE FROM lineage_cache")
        connection.execute("DELETE FROM taxon_names")
        connection.execute("DELETE FROM taxa")
        connection.execute("DELETE FROM metadata")
        if commit:
            connection.commit()


def insert_taxa_rows(
    rows: list[tuple[object, ...]],
    db_path: DatabaseHandle = None,
    *,
    commit: bool = True,
) -> None:
    """Bulk insert parsed taxa rows from `nodes.dmp`."""

    with connect(db_path or get_default_db_path()) as connection:
        connection.executemany(
            """
            INSERT INTO taxa(
                taxid,
                parent_taxid,
                rank,
                is_root,
                source_node_embl_code,
                division_id,
                inherited_div_flag,
                genetic_code_id,
                inherited_gc_flag,
                mitochondrial_genetic_code_id,
                inherited_mgc_flag,
                genbank_hidden_flag,
                hidden_subtree_root_flag,
                comments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        if commit:
            connection.commit()


def insert_taxon_name_rows(
    rows: list[tuple[object, ...]],
    db_path: DatabaseHandle = None,
    *,
    commit: bool = True,
) -> None:
    """Bulk insert parsed taxon name rows from `names.dmp`."""

    with connect(db_path or get_default_db_path()) as connection:
        connection.executemany(
            """
            INSERT INTO taxon_names(
                taxid,
                name_txt,
                unique_name,
                name_class,
                normalized_name
            ) VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        if commit:
            connection.commit()


def insert_lineage_rows(
    rows: list[tuple[object, ...]],
    db_path: DatabaseHandle = None,
    *,
    commit: bool = True,
) -> None:
    """Bulk insert materialized lineage cache rows."""

    with connect(db_path or get_default_db_path()) as connection:
        connection.executemany(
            """
            INSERT INTO lineage_cache(
                taxid,
                lineage_json
            ) VALUES (?, ?)
            """,
            rows,
        )
        if commit:
            connection.commit()


def upsert_metadata(
    db_path: DatabaseHandle,
    items: dict[str, str],
    *,
    commit: bool = True,
) -> None:
    """Persist build metadata used for reproducibility and cache reuse."""

    with connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO metadata(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            items.items(),
        )
        if commit:
            connection.commit()


def get_metadata_value(db_path: DatabaseHandle, key: str) -> str | None:
    """Return one metadata value from the SQLite store if it exists."""

    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT value FROM metadata WHERE key = ?",
            (key,),
        ).fetchone()
    return None if row is None else str(row["value"])


def fetch_all_metadata(db_path: DatabaseHandle) -> dict[str, str]:
    """Return all metadata key/value pairs from the SQLite store."""

    with connect(db_path) as connection:
        rows = connection.execute("SELECT key, value FROM metadata ORDER BY key").fetchall()
    return {str(row["key"]): str(row["value"]) for row in rows}


def insert_reviewed_mapping(db_path: DatabaseHandle, row: tuple[object, ...]) -> None:
    """Persist one reviewed mapping record."""

    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO reviewed_mappings(
                original_name,
                normalized_name,
                provided_level,
                resolved_taxid,
                matched_scientific_name,
                match_type,
                status,
                score,
                decision_action,
                taxonomy_build_version,
                reviewer,
                warnings_json,
                notes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        connection.commit()


def fetch_reusable_reviewed_mapping(
    db_path: DatabaseHandle,
    *,
    normalized_name: str,
    provided_level: str | None,
    taxonomy_build_version: str,
) -> sqlite3.Row | None:
    """Return the latest reviewed mapping eligible for conservative reuse."""

    with connect(db_path) as connection:
        return connection.execute(
            """
            SELECT *
            FROM reviewed_mappings
            WHERE normalized_name = ?
              AND (
                    (provided_level = ?)
                    OR (provided_level IS NULL AND ? IS NULL)
                  )
              AND taxonomy_build_version = ?
              AND decision_action IN ('confirm', 'choose_candidate')
              AND status = 'confirmed_by_user'
              AND resolved_taxid IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (normalized_name, provided_level, provided_level, taxonomy_build_version),
        ).fetchone()


def fetch_name_matches(
    db_path: DatabaseHandle,
    *,
    name_txt: str | None = None,
    normalized_name: str | None = None,
    scientific_only: bool = False,
    exclude_scientific: bool = False,
) -> list[sqlite3.Row]:
    """Return taxon/name matches for exact or normalized deterministic lookup."""

    predicates: list[str] = []
    parameters: list[object] = []
    index_hint = ""

    if name_txt is not None:
        predicates.append("n.name_txt = ?")
        parameters.append(name_txt)
        index_hint = "INDEXED BY idx_taxon_names_name_txt"
    if normalized_name is not None:
        predicates.append("n.normalized_name = ?")
        parameters.append(normalized_name)
        if not index_hint:
            index_hint = "INDEXED BY idx_taxon_names_normalized_name"
    if scientific_only:
        predicates.append("n.name_class = 'scientific name'")
    if exclude_scientific:
        predicates.append("n.name_class <> 'scientific name'")

    where_clause = " AND ".join(predicates) if predicates else "1 = 1"
    query = f"""
        SELECT
            n.taxid,
            n.name_txt AS matched_name,
            n.name_class,
            t.rank,
            sci.name_txt AS scientific_name,
            lc.lineage_json
        FROM taxon_names AS n {index_hint}
        JOIN taxa AS t
            ON t.taxid = n.taxid
        LEFT JOIN taxon_names AS sci
            ON sci.taxid = n.taxid
           AND sci.name_class = 'scientific name'
        LEFT JOIN lineage_cache AS lc
            ON lc.taxid = n.taxid
        WHERE {where_clause}
    """

    with connect(db_path) as connection:
        return list(connection.execute(query, parameters).fetchall())


def fetch_lineage_entries(db_path: DatabaseHandle, taxid: int) -> list[dict[str, object]]:
    """Return cached lineage entries for one taxid from the materialized cache."""

    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT lineage_json FROM lineage_cache WHERE taxid = ?",
            (taxid,),
        ).fetchone()

    if row is None:
        return []
    return list(json.loads(row["lineage_json"]))


def fetch_fuzzy_name_pool(
    db_path: DatabaseHandle,
    normalized_name: str,
    *,
    limit: int = 1000,
) -> list[sqlite3.Row]:
    """Return a narrowed candidate pool for supervised fuzzy suggestion.

    This keeps the primary retrieval path on indexed scientific-name prefixes.
    A smaller internal-token fallback is used only when the anchored prefix does
    not produce enough rows.
    """

    tokens = [token for token in normalized_name.split() if len(token) >= 3]
    primary_prefix = ""
    internal_prefix = ""
    if tokens:
        primary_prefix = tokens[0][: min(len(tokens[0]), 6)]
        if len(tokens) > 1:
            internal_prefix = tokens[1][: min(len(tokens[1]), 6)]
    elif normalized_name:
        primary_prefix = normalized_name[: min(len(normalized_name), 6)]

    if not primary_prefix:
        return []

    primary_query = """
        SELECT
            n.taxid,
            n.name_txt AS matched_name,
            n.normalized_name,
            n.name_class,
            t.rank,
            sci.name_txt AS scientific_name,
            lc.lineage_json
        FROM taxon_names AS n INDEXED BY idx_taxon_names_normalized_name
        JOIN taxa AS t
            ON t.taxid = n.taxid
        LEFT JOIN taxon_names AS sci
            ON sci.taxid = n.taxid
           AND sci.name_class = 'scientific name'
        LEFT JOIN lineage_cache AS lc
            ON lc.taxid = n.taxid
        WHERE n.name_class = 'scientific name'
          AND n.normalized_name >= ?
          AND n.normalized_name < ?
        LIMIT ?
    """
    fallback_query = """
        SELECT
            n.taxid,
            n.name_txt AS matched_name,
            n.normalized_name,
            n.name_class,
            t.rank,
            sci.name_txt AS scientific_name,
            lc.lineage_json
        FROM taxon_names AS n
        JOIN taxa AS t
            ON t.taxid = n.taxid
        LEFT JOIN taxon_names AS sci
            ON sci.taxid = n.taxid
           AND sci.name_class = 'scientific name'
        LEFT JOIN lineage_cache AS lc
            ON lc.taxid = n.taxid
        WHERE n.name_class = 'scientific name'
          AND n.normalized_name LIKE ?
        LIMIT ?
    """

    with connect(db_path) as connection:
        rows = list(
            connection.execute(
                primary_query,
                (primary_prefix, f"{primary_prefix}\uffff", limit),
            ).fetchall()
        )
        if internal_prefix and len(rows) < limit:
            remaining = limit - len(rows)
            rows.extend(
                connection.execute(
                    fallback_query,
                    (f"% {internal_prefix}%", remaining),
                ).fetchall()
            )

    unique_rows: list[sqlite3.Row] = []
    seen_keys: set[tuple[int, str]] = set()
    for row in rows:
        key = (int(row["taxid"]), str(row["matched_name"]))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_rows.append(row)
        if len(unique_rows) >= limit:
            break
    return unique_rows
