"""Local Disbiome DB acquisition: fetch the keyless JSON tables once, join, and
build a small SQLite that the ``local`` backend serves offline.

Disbiome has no bulk dump file, but its API returns each table whole in a single
GET and the whole dataset is ~7 MB, so "download" here means fetching a handful of
endpoints. The generic acquisition plumbing (consent gate, cross-process lock,
disk precheck, atomic publish) lives in ``braidworks.core.localdb``; this module
supplies only the domain pieces — ``db_is_valid`` and ``_build`` — plus the join.

Tables fetched: ``/experiment`` (the associations) joined to ``/disease``,
``/organism`` and ``/publication`` by their ``*_id`` fields. ``/sample`` and
``/method`` are just ``{id, name}`` and already denormalized onto each experiment
(``sample_name`` / ``method_name``), so they are not fetched separately.

Disbiome encodes missing values as the string ``"None"``; ``_clean`` normalizes
those to ``None``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from braidworks.core import BackendConfigurationError
from braidworks.core.localdb import ProgressCallback, default_db_path, ensure_local_db

API_BASE = "https://disbiome.ugent.be:8080"
NAMESPACE = "disbiome"
DB_FILENAME = "disbiome.sqlite"
_FETCH_TIMEOUT = 180  # seconds; /experiment is ~5.8 MB

_CONSENT_MESSAGE = (
    "disbiome_weaver's local DB is not built yet ({path}).\n"
    "It is small (~7 MB fetched from the keyless Disbiome API, builds in seconds), "
    "but acquisition is opt-in. To build it, either:\n"
    "  - call build_disbiome_weaver_configured(auto_setup=True), or\n"
    "  - set BRAIDWORKS_AUTO_DOWNLOAD=1, or\n"
    "  - call disbiome_weaver.setup.ensure_disbiome_db(auto=True).\n"
    "Override the location with db_path=... or the BRAIDWORKS_DATA_DIR env var."
)


def default_disbiome_db_path() -> Path:
    """Per-user default DB path (override via ``BRAIDWORKS_DATA_DIR``)."""
    return default_db_path(NAMESPACE, DB_FILENAME)


def _clean(value: Any) -> Any:
    """Disbiome uses the string ``"None"`` (and ``""``) for missing — normalize to None."""
    if isinstance(value, str):
        stripped = value.strip()
        return None if stripped in ("", "None") else stripped
    return value


def _coerce_taxid(value: Any) -> int | None:
    """Coerce a consumed ``ncbi.taxon.id`` (int or digit-string) to int, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def join_record(
    experiment: dict[str, Any],
    diseases: dict[str, dict],
    organisms: dict[str, dict],
    publications: dict[str, dict],
) -> dict[str, Any]:
    """One experiment + its joined disease / organism / publication, all cleaned."""
    record = {k: _clean(v) for k, v in experiment.items()}

    def _clean_row(row: dict | None) -> dict | None:
        return {k: _clean(v) for k, v in row.items()} if row else None

    record["disease"] = _clean_row(diseases.get(str(_coerce_taxid(experiment.get("disease_id")))))
    record["organism"] = _clean_row(
        organisms.get(str(_coerce_taxid(experiment.get("organism_id"))))
    )
    record["publication"] = _clean_row(
        publications.get(str(_coerce_taxid(experiment.get("publication_id"))))
    )
    return record


def _content_hash(*collections: Any) -> str:
    digest = hashlib.sha256()
    for coll in collections:
        digest.update(json.dumps(coll, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


def _validate_tables(**tables: Any) -> tuple[dict[str, dict[str, dict]], dict[str, Any]]:
    """Validate source identity before opening the destination; never overwrite duplicates."""
    indexes = {}
    coverage = {}
    for name, rows in tables.items():
        if not isinstance(rows, list):
            raise BackendConfigurationError(f"Disbiome {name}: expected a JSON array")
        index = {}
        for row in rows:
            if not isinstance(row, dict):
                raise BackendConfigurationError(f"Disbiome {name}: expected object rows")
            identity = _coerce_taxid(row.get(f"{name}_id"))
            if identity is None or not 0 < identity <= 2**63 - 1:
                raise BackendConfigurationError(f"Disbiome {name}: invalid primary identity")
            key = str(identity)
            if key in index:
                raise BackendConfigurationError(f"Disbiome {name}: duplicate identity {key}")
            index[key] = row
        indexes[name] = index
        coverage[name] = {"rows": len(rows), "sha256": _content_hash(rows)}
    missing = {name: 0 for name in ("disease", "organism", "publication")}
    for row in tables["experiment"]:
        for name in missing:
            raw = _clean(row.get(f"{name}_id"))
            if raw is None:
                missing[name] += 1
                continue
            identity = _coerce_taxid(raw)
            if identity is None or str(identity) not in indexes[name]:
                raise BackendConfigurationError(
                    f"Disbiome experiment {row['experiment_id']}: dangling {name} identity {raw!r}"
                )
        raw = _clean(row.get("organism_ncbi_id"))
        if raw is not None:
            identity = _coerce_taxid(raw)
            if identity is None or not 0 < identity <= 2**63 - 1:
                raise BackendConfigurationError("Disbiome experiment: invalid NCBI taxid")
    coverage["missing_foreign_identity"] = missing
    coverage["snapshot_consistency"] = "independent table responses; not a frozen snapshot"
    return indexes, coverage


def write_db(
    target: Path,
    *,
    experiments: list[dict],
    diseases: list[dict],
    organisms: list[dict],
    publications: list[dict],
) -> None:
    """Build the SQLite at ``target`` from already-fetched (or canned) tables.

    Shared by the live build (``_build``) and the test fixture, so the schema and
    join live in one place. One row per experiment; ``ncbi_id`` is the join key the
    backend queries on (NULL when an experiment has no NCBI taxid).
    """
    indexes, coverage = _validate_tables(
        experiment=experiments, disease=diseases, organism=organisms, publication=publications
    )
    diseases_by_id = indexes["disease"]
    organisms_by_id = indexes["organism"]
    publications_by_id = indexes["publication"]

    content = _content_hash(
        sorted(experiments, key=lambda e: int(e["experiment_id"])),
        sorted(diseases, key=lambda d: int(d["disease_id"])),
        sorted(organisms, key=lambda o: int(o["organism_id"])),
        sorted(publications, key=lambda p: int(p["publication_id"])),
    )

    con = sqlite3.connect(target)
    try:
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.execute(
            "CREATE TABLE association (ncbi_id INTEGER, experiment_id INTEGER UNIQUE NOT NULL, full_json TEXT, "
            "disease_name, meddra_id, meddra_level, qualitative_outcome, "
            "sample_name, host_type, method_name, publication_id, organism_id, disease_id)"
        )
        rows = []
        n_with_taxid = 0
        for exp in experiments:
            ncbi_id = _coerce_taxid(exp.get("organism_ncbi_id"))
            if ncbi_id is not None:
                n_with_taxid += 1
            joined = join_record(exp, diseases_by_id, organisms_by_id, publications_by_id)
            rows.append(
                (
                    ncbi_id,
                    int(exp["experiment_id"]),
                    json.dumps(joined, ensure_ascii=False),
                    *(
                        joined.get(key)
                        for key in (
                            "disease_name",
                            "meddra_id",
                            "meddra_level",
                            "qualitative_outcome",
                            "sample_name",
                            "host_type",
                            "method_name",
                            "publication_id",
                            "organism_id",
                            "disease_id",
                        )
                    ),
                )
            )
        con.executemany(
            "INSERT INTO association VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
        )
        con.execute("CREATE INDEX ix_association_ncbi ON association(ncbi_id)")
        con.execute("CREATE INDEX ix_association_summary ON association(ncbi_id, disease_name)")
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("schema_version", "3"),
                ("build_id", uuid.uuid4().hex),
                ("content_sha256", content),
                ("n_experiments", str(len(experiments))),
                ("n_with_taxid", str(n_with_taxid)),
                ("source", API_BASE),
                ("build_completed_utc", datetime.now(UTC).isoformat()),
                ("source_coverage", json.dumps(coverage, sort_keys=True)),
            ],
        )
        con.commit()
    finally:
        con.close()


def db_is_valid(path: Path) -> bool:
    """A usable, fully-built Disbiome DB: has the meta hash and non-empty associations."""
    if not path.exists():
        return False
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        schema = con.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        if schema != ("3",):
            return False
        con.execute(
            "SELECT disease_name, meddra_id, meddra_level, qualitative_outcome, sample_name, host_type, method_name, publication_id, organism_id, disease_id FROM association LIMIT 0"
        )
        has_hash = con.execute("SELECT value FROM meta WHERE key = 'content_sha256'").fetchone()
        count = con.execute("SELECT COUNT(*) FROM association").fetchone()[0]
        return bool(has_hash) and count > 0
    except sqlite3.Error:
        return False
    finally:
        con.close()


def _fetch(endpoint: str) -> list[dict]:
    url = f"{API_BASE}/{endpoint}"
    with urllib.request.urlopen(url, timeout=_FETCH_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _build(target: Path, *, fetch: Callable[[str], list[dict]] = _fetch) -> None:
    """Fetch the Disbiome tables and write the SQLite at ``target`` (``fetch`` injectable)."""
    write_db(
        target,
        experiments=fetch("experiment"),
        diseases=fetch("disease"),
        organisms=fetch("organism"),
        publications=fetch("publication"),
    )


def ensure_disbiome_db(
    db_path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    progress: ProgressCallback | None = None,
) -> Path:
    """Ensure a valid local Disbiome SQLite exists, building it if consented.

    Idempotent: a valid DB is returned instantly. Otherwise acquisition needs
    consent (``auto`` or ``BRAIDWORKS_AUTO_DOWNLOAD``); without it, an actionable
    ``BackendConfigurationError`` is raised. ``progress`` emits table-fetch and database-write events; byte totals are unknown.
    """
    path = Path(db_path) if db_path else default_disbiome_db_path()

    def build(target: Path) -> None:
        def fetch_table(endpoint: str) -> list[dict]:
            if progress:
                progress("fetch", endpoint, 0, None, False)
            records = _fetch(endpoint)
            if progress:
                progress("fetch", endpoint, 0, None, True)
            return records

        if progress:
            progress("build", "Disbiome database", 0, None, False)
        _build(target, fetch=fetch_table)
        if progress:
            progress("build", "Disbiome database", 0, None, True)

    return ensure_local_db(
        path,
        is_valid=db_is_valid,
        build=build,
        consent_message=_CONSENT_MESSAGE.format(path=path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=200_000_000,  # ~7 MB data; generous headroom for the temp build
    )


def iter_associations(
    db_path: str | Path | None = None, *, auto: bool = False
) -> Iterator[dict[str, Any]]:
    """Yield every Disbiome microbe–disease association as a flat record — the bulk view.

    The ``fetch`` capability answers "this microbe's diseases" per taxid; this is its
    bulk counterpart, for an ingestion that needs the *whole* association table (e.g. to
    seed a union node set over all Disbiome taxa). Ensures the local DB (consent-gated,
    like the backend), then streams every experiment carrying an NCBI taxid. Each record::

        {taxid, meddra_id, meddra_level, disease_name, outcome, experiment_id}

    ``outcome`` is Disbiome's raw qualitative outcome ("Elevated" / "Reduced"); missing
    fields are already normalized to ``None``. Experiments without a taxid are skipped —
    there is no organism to key on.
    """
    path = ensure_disbiome_db(db_path, auto=auto)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cursor = con.execute(
            "SELECT ncbi_id, full_json FROM association "
            "WHERE ncbi_id IS NOT NULL ORDER BY experiment_id"
        )
        for ncbi_id, full_json in cursor:
            record = json.loads(full_json)
            yield {
                "taxid": int(ncbi_id),
                "meddra_id": record.get("meddra_id"),
                "meddra_level": record.get("meddra_level"),
                "disease_name": record.get("disease_name"),
                "outcome": record.get("qualitative_outcome"),
                "experiment_id": record.get("experiment_id"),
            }
    finally:
        con.close()
