"""Reviewed mapping cache interface.

Phase 9 implements conservative reuse rules and storage-backed
lookup/write behavior.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .db import (
    fetch_reusable_reviewed_mapping,
    get_metadata_value,
    initialize_database,
    insert_reviewed_mapping,
)
from .normalize import normalize_level, normalize_name
from .policy import MatchType, ResolutionStatus, WarningCode
from .schemas import DecisionAction, DecisionRecord, ResolveRequest

_INITIALIZED_CACHE_DATABASES: set[tuple[str, str | int]] = set()
DatabaseHandle = sqlite3.Connection | Path | str


def _resolve_cache_db_path(
    taxonomy_db_path: DatabaseHandle,
    cache_db_path: DatabaseHandle | None,
) -> DatabaseHandle:
    """Resolve the SQLite path used for reviewed mapping persistence."""

    return cache_db_path if cache_db_path is not None else taxonomy_db_path


def _cache_key(db_path: DatabaseHandle) -> tuple[str, str | int]:
    """Return a stable in-process key for one cache backend."""

    if isinstance(db_path, sqlite3.Connection):
        return ("connection", id(db_path))
    return ("path", str(Path(db_path).resolve()))


def _ensure_cache_database(db_path: DatabaseHandle, *, create_indexes: bool) -> None:
    """Initialize the cache schema once per process for each SQLite file."""

    key = _cache_key(db_path)
    if key in _INITIALIZED_CACHE_DATABASES:
        return
    initialize_database(db_path, create_indexes=create_indexes)
    _INITIALIZED_CACHE_DATABASES.add(key)


def lookup_reviewed_mapping(
    request: ResolveRequest,
    *,
    taxonomy_db_path: DatabaseHandle,
    cache_db_path: DatabaseHandle | None = None,
    taxonomy_build_version: str | None = None,
    create_cache_indexes: bool = True,
) -> DecisionRecord | None:
    """Return a conservatively reusable reviewed mapping if one is available.

    Current reuse rules are intentionally strict:

    - same normalized name
    - same normalized provided level, including both null
    - same taxonomy build version
    - prior reviewed decision was a confirm-like action
    - prior reviewed status is `confirmed_by_user`
    """

    resolved_cache_db_path = _resolve_cache_db_path(taxonomy_db_path, cache_db_path)
    _ensure_cache_database(
        resolved_cache_db_path,
        create_indexes=create_cache_indexes,
    )
    if taxonomy_build_version is None:
        taxonomy_build_version = get_metadata_value(taxonomy_db_path, "taxonomy_build_version")
    if taxonomy_build_version is None:
        return None

    row = fetch_reusable_reviewed_mapping(
        resolved_cache_db_path,
        normalized_name=normalize_name(request.original_name),
        provided_level=normalize_level(request.provided_level),
        taxonomy_build_version=taxonomy_build_version,
    )
    if row is None:
        return None

    return DecisionRecord(
        action=DecisionAction(str(row["decision_action"])),
        original_name=row["original_name"],
        normalized_name=row["normalized_name"],
        provided_level=row["provided_level"],
        taxonomy_build_version=row["taxonomy_build_version"],
        reviewer=row["reviewer"],
        resolved_taxid=row["resolved_taxid"],
        matched_scientific_name=row["matched_scientific_name"],
        match_type=MatchType(str(row["match_type"])),
        status=ResolutionStatus(str(row["status"])),
        score=row["score"],
        warnings=[WarningCode(value) for value in json.loads(row["warnings_json"])],
        notes=row["notes"],
        created_at=row["created_at"],
    )


def record_reviewed_mapping(
    decision: DecisionRecord,
    *,
    taxonomy_db_path: DatabaseHandle,
    cache_db_path: DatabaseHandle | None = None,
    create_cache_indexes: bool = True,
) -> None:
    """Persist a reviewed mapping decision for later conservative reuse."""

    resolved_cache_db_path = _resolve_cache_db_path(taxonomy_db_path, cache_db_path)
    _ensure_cache_database(
        resolved_cache_db_path,
        create_indexes=create_cache_indexes,
    )
    insert_reviewed_mapping(
        resolved_cache_db_path,
        (
            decision.original_name,
            normalize_name(decision.original_name)
            if not decision.normalized_name
            else decision.normalized_name,
            normalize_level(decision.provided_level),
            decision.resolved_taxid,
            decision.matched_scientific_name,
            decision.match_type.value,
            decision.status.value,
            decision.score,
            decision.action.value,
            decision.taxonomy_build_version,
            decision.reviewer,
            json.dumps([warning.value for warning in decision.warnings]),
            decision.notes,
            decision.created_at,
        ),
    )
