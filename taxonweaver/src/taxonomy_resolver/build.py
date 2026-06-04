"""NCBI taxdump ingestion and SQLite reference database build helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from tarfile import TarFile, TarInfo, is_tarfile
from typing import BinaryIO, Iterator

from .db import (
    clear_reference_tables,
    connect,
    initialize_database,
    insert_lineage_rows,
    insert_taxa_rows,
    insert_taxon_name_rows,
    upsert_metadata,
)
from .normalize import normalize_name

REQUIRED_TAXDUMP_MEMBERS = {"names.dmp", "nodes.dmp"}
ProgressCallback = Callable[[str, str, int | None, int | None, bool], None]
BUILD_PRAGMA_STATEMENTS = (
    "PRAGMA journal_mode = OFF",
    "PRAGMA synchronous = OFF",
    "PRAGMA temp_store = MEMORY",
)
RUNTIME_PRAGMA_STATEMENTS = (
    "PRAGMA journal_mode = DELETE",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA temp_store = DEFAULT",
)


@dataclass(slots=True)
class TaxonomyBuildSummary:
    """Compact build report returned by the database builder."""

    db_path: str
    taxonomy_build_version: str
    source_dump_path: str
    source_dump_sha256: str
    built_at_utc: str
    schema_version: str
    taxa_count: int
    name_count: int
    scientific_name_count: int
    synonym_count: int
    lineage_cache_count: int
    root_taxid_count: int
    rankedlineage_present: bool
    validation_checks: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready report suitable for docs, logs, and tests."""

        return asdict(self)


def sha256_file(path: Path) -> str:
    """Calculate a stable digest for reproducibility metadata."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_taxdump_archive(archive_path: Path) -> set[str]:
    """Confirm that the expected NCBI dump files exist before parsing."""

    if not is_tarfile(archive_path):
        raise ValueError(f"{archive_path} is not a valid tar archive.")

    with TarFile.open(archive_path) as archive:
        members = {Path(member.name).name for member in archive.getmembers()}

    missing = sorted(REQUIRED_TAXDUMP_MEMBERS - members)
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Taxdump archive is missing required files: {missing_text}")

    return members


def _find_member(archive: TarFile, basename: str) -> TarInfo:
    """Return the tar member matching the requested dump filename."""

    for member in archive.getmembers():
        if Path(member.name).name == basename:
            return member
    raise KeyError(f"Archive member {basename} not found.")


def _iter_dmp_rows(handle: BinaryIO) -> Iterator[list[str]]:
    """Yield pipe-delimited NCBI dump rows as stripped string fields."""

    for raw_line in handle:
        line = raw_line.decode("utf-8").rstrip("\n")
        parts = line.split("\t|\t")
        parts[-1] = parts[-1].removesuffix("\t|").strip()
        yield [part.strip() for part in parts]


def _build_taxonomy_version(built_at_utc: str, source_dump_sha256: str) -> str:
    """Create a stable build version identifier for cache and audit use."""

    date_part = built_at_utc[:10]
    return f"ncbi-taxonomy-{date_part}-{source_dump_sha256[:12]}"


def _notify_progress(
    callback: ProgressCallback | None,
    *,
    stage: str,
    message: str,
    current: int | None = None,
    total: int | None = None,
    final: bool = False,
) -> None:
    """Send a progress event if a callback was provided."""

    if callback is not None:
        callback(stage, message, current, total, final)


def _insert_nodes(
    archive: TarFile,
    *,
    db_handle: sqlite3.Connection,
    batch_size: int = 50_000,
    progress_callback: ProgressCallback | None = None,
    progress_every: int = 250_000,
) -> tuple[dict[int, int], dict[int, str], int]:
    """Parse and insert `nodes.dmp`, returning parent and rank lookup maps."""

    member = _find_member(archive, "nodes.dmp")
    parent_by_taxid: dict[int, int] = {}
    rank_by_taxid: dict[int, str] = {}
    row_count = 0
    batch: list[tuple[object, ...]] = []

    extracted = archive.extractfile(member)
    if extracted is None:
        raise ValueError("Unable to read nodes.dmp from the taxdump archive.")

    with extracted:
        for fields in _iter_dmp_rows(extracted):
            taxid = int(fields[0])
            parent_taxid = int(fields[1])
            rank = fields[2]
            parent_by_taxid[taxid] = parent_taxid
            rank_by_taxid[taxid] = rank
            batch.append(
                (
                    taxid,
                    parent_taxid,
                    rank,
                    int(taxid == parent_taxid),
                    fields[3],
                    int(fields[4]),
                    int(fields[5]),
                    int(fields[6]),
                    int(fields[7]),
                    int(fields[8]),
                    int(fields[9]),
                    int(fields[10]),
                    int(fields[11]),
                    fields[12],
                )
            )
            row_count += 1

            if len(batch) >= batch_size:
                insert_taxa_rows(batch, db_handle, commit=False)
                batch.clear()

            if row_count % progress_every == 0:
                _notify_progress(
                    progress_callback,
                    stage="nodes",
                    message="Loading nodes.dmp",
                    current=row_count,
                )

    if batch:
        insert_taxa_rows(batch, db_handle, commit=False)

    _notify_progress(
        progress_callback,
        stage="nodes",
        message="Loaded nodes.dmp",
        current=row_count,
        final=True,
    )

    return parent_by_taxid, rank_by_taxid, row_count


def _insert_names(
    archive: TarFile,
    *,
    db_handle: sqlite3.Connection,
    batch_size: int = 50_000,
    progress_callback: ProgressCallback | None = None,
    progress_every: int = 250_000,
) -> tuple[dict[int, str], int, int, int]:
    """Parse and insert `names.dmp`, tracking scientific names for each taxid."""

    member = _find_member(archive, "names.dmp")
    scientific_name_by_taxid: dict[int, str] = {}
    total_names = 0
    scientific_names = 0
    synonym_names = 0
    batch: list[tuple[object, ...]] = []

    extracted = archive.extractfile(member)
    if extracted is None:
        raise ValueError("Unable to read names.dmp from the taxdump archive.")

    with extracted:
        for fields in _iter_dmp_rows(extracted):
            taxid = int(fields[0])
            name_txt = fields[1]
            unique_name = fields[2] or None
            name_class = fields[3]
            normalized_name = normalize_name(name_txt)
            batch.append((taxid, name_txt, unique_name, name_class, normalized_name))
            total_names += 1

            if name_class == "scientific name":
                scientific_name_by_taxid[taxid] = name_txt
                scientific_names += 1
            else:
                synonym_names += 1

            if len(batch) >= batch_size:
                insert_taxon_name_rows(batch, db_handle, commit=False)
                batch.clear()

            if total_names % progress_every == 0:
                _notify_progress(
                    progress_callback,
                    stage="names",
                    message="Loading names.dmp",
                    current=total_names,
                )

    if batch:
        insert_taxon_name_rows(batch, db_handle, commit=False)

    _notify_progress(
        progress_callback,
        stage="names",
        message="Loaded names.dmp",
        current=total_names,
        final=True,
    )

    return scientific_name_by_taxid, total_names, scientific_names, synonym_names


def _lineage_row(
    taxid: int,
    lineage: list[dict[str, object]],
) -> tuple[object, ...]:
    """Convert one lineage list into the compact cache row shape."""

    compact_lineage = [
        [int(entry["taxid"]), str(entry["rank"]), str(entry["name"])]
        for entry in lineage
    ]
    return (
        taxid,
        json.dumps(compact_lineage, ensure_ascii=True, separators=(",", ":")),
    )


def _iter_lineage_rows(
    parent_by_taxid: dict[int, int],
    rank_by_taxid: dict[int, str],
    scientific_name_by_taxid: dict[int, str],
) -> Iterator[tuple[object, ...]]:
    """Yield lineage cache rows by walking the taxonomy tree once.

    This keeps memory bounded to the current traversal path instead of caching a
    full lineage list for every taxid in memory at once.
    """

    children_by_parent: dict[int, list[int]] = defaultdict(list)
    root_taxids: list[int] = []

    for taxid, parent_taxid in parent_by_taxid.items():
        if taxid == parent_taxid or parent_taxid not in parent_by_taxid:
            root_taxids.append(taxid)
        else:
            children_by_parent[parent_taxid].append(taxid)

    for child_taxids in children_by_parent.values():
        child_taxids.sort()
    root_taxids.sort()

    for root_taxid in root_taxids:
        yield from _walk_lineage_tree(
            root_taxid,
            [],
            children_by_parent,
            rank_by_taxid,
            scientific_name_by_taxid,
        )


def _walk_lineage_tree(
    taxid: int,
    lineage_prefix: list[dict[str, object]],
    children_by_parent: dict[int, list[int]],
    rank_by_taxid: dict[int, str],
    scientific_name_by_taxid: dict[int, str],
) -> Iterator[tuple[object, ...]]:
    """Depth-first walk that emits one lineage cache row per taxid."""

    current_lineage = list(lineage_prefix)
    current_name = scientific_name_by_taxid.get(taxid)
    if current_name:
        current_lineage.append(
            {"taxid": taxid, "rank": rank_by_taxid[taxid], "name": current_name}
        )

    yield _lineage_row(taxid, current_lineage)

    for child_taxid in children_by_parent.get(taxid, []):
        yield from _walk_lineage_tree(
            child_taxid,
            current_lineage,
            children_by_parent,
            rank_by_taxid,
            scientific_name_by_taxid,
        )


def _insert_lineage_cache(
    parent_by_taxid: dict[int, int],
    rank_by_taxid: dict[int, str],
    scientific_name_by_taxid: dict[int, str],
    *,
    db_handle: sqlite3.Connection,
    batch_size: int = 25_000,
    progress_callback: ProgressCallback | None = None,
    progress_every: int = 250_000,
) -> int:
    """Materialize lineage cache rows for every taxon."""

    row_count = 0
    batch: list[tuple[object, ...]] = []

    for row in _iter_lineage_rows(parent_by_taxid, rank_by_taxid, scientific_name_by_taxid):
        batch.append(row)
        row_count += 1
        if len(batch) >= batch_size:
            insert_lineage_rows(batch, db_handle, commit=False)
            batch.clear()
        if row_count % progress_every == 0:
            _notify_progress(
                progress_callback,
                stage="lineage",
                message="Materializing lineage cache",
                current=row_count,
            )

    if batch:
        insert_lineage_rows(batch, db_handle, commit=False)

    _notify_progress(
        progress_callback,
        stage="lineage",
        message="Materialized lineage cache",
        current=row_count,
        final=True,
    )

    return row_count


def _apply_sqlite_pragmas(
    connection: sqlite3.Connection,
    statements: tuple[str, ...],
) -> None:
    """Apply one sequence of SQLite PRAGMA statements."""

    for statement in statements:
        connection.execute(statement)


def _count_rows(table_name: str, db_handle: sqlite3.Connection) -> int:
    """Return row counts used by build validation and tests."""

    row = db_handle.execute(f"SELECT COUNT(*) AS row_count FROM {table_name}").fetchone()
    return int(row["row_count"])


def _get_root_taxid_count(db_handle: sqlite3.Connection) -> int:
    """Return the number of root rows present in the loaded taxonomy."""

    row = db_handle.execute(
        "SELECT COUNT(*) AS row_count FROM taxa WHERE is_root = 1"
    ).fetchone()
    return int(row["row_count"])


def _validate_build(
    *,
    db_handle: sqlite3.Connection,
    expected_taxa_count: int,
    expected_name_count: int,
    expected_scientific_name_count: int,
) -> dict[str, bool]:
    """Run lightweight deterministic checks on the built reference DB."""

    taxa_count = _count_rows("taxa", db_handle)
    name_count = _count_rows("taxon_names", db_handle)
    lineage_cache_count = _count_rows("lineage_cache", db_handle)
    root_taxid_count = _get_root_taxid_count(db_handle)

    scientific_name_count = int(
        db_handle.execute(
            """
            SELECT COUNT(*) AS row_count
            FROM taxon_names
            WHERE name_class = 'scientific name'
            """
        ).fetchone()["row_count"]
    )

    return {
        "taxa_loaded": taxa_count == expected_taxa_count and taxa_count > 0,
        "names_loaded": name_count == expected_name_count and name_count > 0,
        "scientific_names_loaded": (
            scientific_name_count == expected_scientific_name_count
            and scientific_name_count > 0
        ),
        "lineage_cache_complete": lineage_cache_count == expected_taxa_count,
        "root_present": root_taxid_count >= 1,
    }


def _optimize_database(
    db_handle: sqlite3.Connection,
    *,
    progress_callback: ProgressCallback | None = None,
) -> None:
    """Refresh SQLite planner statistics after the build completes."""

    _notify_progress(
        progress_callback,
        stage="optimize",
        message="Analyzing SQLite statistics",
        final=True,
    )
    db_handle.execute("ANALYZE")
    _notify_progress(
        progress_callback,
        stage="optimize",
        message="Running SQLite optimizer",
        final=True,
    )
    db_handle.execute("PRAGMA optimize")
    db_handle.commit()


def build_taxonomy_database(
    dump_path: Path | str,
    db_path: Path | str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> TaxonomyBuildSummary:
    """Build the SQLite taxonomy reference database from an NCBI taxdump archive."""

    dump_path = Path(dump_path)
    db_path = Path(db_path)
    _notify_progress(
        progress_callback,
        stage="prepare",
        message="Validating taxdump archive",
        final=True,
    )
    available_members = validate_taxdump_archive(dump_path)
    _notify_progress(
        progress_callback,
        stage="prepare",
        message="Initializing SQLite schema",
        final=True,
    )
    built_at_utc = datetime.now(timezone.utc).isoformat()
    source_dump_sha256 = sha256_file(dump_path)
    taxonomy_build_version = _build_taxonomy_version(built_at_utc, source_dump_sha256)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    initialize_database(db_path, create_indexes=False)
    with connect(db_path) as build_connection:
        _notify_progress(
            progress_callback,
            stage="prepare",
            message="Applying SQLite build pragmas",
            final=True,
        )
        _apply_sqlite_pragmas(build_connection, BUILD_PRAGMA_STATEMENTS)
        clear_reference_tables(build_connection, commit=False)
        build_connection.commit()

        with TarFile.open(dump_path) as archive:
            _notify_progress(
                progress_callback,
                stage="nodes",
                message="Starting nodes.dmp load",
                current=0,
            )
            parent_by_taxid, rank_by_taxid, taxa_count = _insert_nodes(
                archive,
                db_handle=build_connection,
                progress_callback=progress_callback,
            )
            build_connection.commit()
            _notify_progress(
                progress_callback,
                stage="names",
                message="Starting names.dmp load",
                current=0,
            )
            scientific_name_by_taxid, name_count, scientific_name_count, synonym_count = _insert_names(
                archive,
                db_handle=build_connection,
                progress_callback=progress_callback,
            )
            build_connection.commit()

        _notify_progress(
            progress_callback,
            stage="lineage",
            message="Starting lineage cache materialization",
            current=0,
            total=taxa_count,
        )
        lineage_cache_count = _insert_lineage_cache(
            parent_by_taxid=parent_by_taxid,
            rank_by_taxid=rank_by_taxid,
            scientific_name_by_taxid=scientific_name_by_taxid,
            db_handle=build_connection,
            progress_callback=progress_callback,
        )
        build_connection.commit()
        _notify_progress(
            progress_callback,
            stage="indexes",
            message="Creating SQLite indexes",
            final=True,
        )
        initialize_database(build_connection, create_indexes=True)
        _optimize_database(
            build_connection,
            progress_callback=progress_callback,
        )
        _notify_progress(
            progress_callback,
            stage="validate",
            message="Running validation checks",
            final=True,
        )
        validation_checks = _validate_build(
            db_handle=build_connection,
            expected_taxa_count=taxa_count,
            expected_name_count=name_count,
            expected_scientific_name_count=scientific_name_count,
        )
        root_taxid_count = _get_root_taxid_count(build_connection)

        _notify_progress(
            progress_callback,
            stage="metadata",
            message="Writing build metadata",
            final=True,
        )
        upsert_metadata(
            build_connection,
            {
                "schema_version": "1",
                "build_stage": "phase_2_complete",
                "taxonomy_build_version": taxonomy_build_version,
                "source_dump_path": str(dump_path),
                "source_dump_sha256": source_dump_sha256,
                "built_at_utc": built_at_utc,
                "taxa_count": str(taxa_count),
                "name_count": str(name_count),
                "scientific_name_count": str(scientific_name_count),
                "synonym_count": str(synonym_count),
                "lineage_cache_count": str(lineage_cache_count),
                "root_taxid_count": str(root_taxid_count),
                "rankedlineage_present": str("rankedlineage.dmp" in available_members).lower(),
                "sqlite_build_pragmas_json": json.dumps(BUILD_PRAGMA_STATEMENTS),
                "sqlite_post_build_optimized": "true",
                "validation_checks_json": json.dumps(
                    validation_checks, ensure_ascii=True, separators=(",", ":")
                ),
            },
        )
        _notify_progress(
            progress_callback,
            stage="prepare",
            message="Restoring SQLite runtime pragmas",
            final=True,
        )
        _apply_sqlite_pragmas(build_connection, RUNTIME_PRAGMA_STATEMENTS)
        build_connection.commit()
        _notify_progress(
            progress_callback,
            stage="done",
            message="Build complete",
            final=True,
        )

    return TaxonomyBuildSummary(
        db_path=str(db_path),
        taxonomy_build_version=taxonomy_build_version,
        source_dump_path=str(dump_path),
        source_dump_sha256=source_dump_sha256,
        built_at_utc=built_at_utc,
        schema_version="1",
        taxa_count=taxa_count,
        name_count=name_count,
        scientific_name_count=scientific_name_count,
        synonym_count=synonym_count,
        lineage_cache_count=lineage_cache_count,
        root_taxid_count=root_taxid_count,
        rankedlineage_present="rankedlineage.dmp" in available_members,
        validation_checks=validation_checks,
    )
