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
from pathlib import Path
from typing import Any, Callable

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

    record["disease"] = _clean_row(diseases.get(str(experiment.get("disease_id"))))
    record["organism"] = _clean_row(organisms.get(str(experiment.get("organism_id"))))
    record["publication"] = _clean_row(publications.get(str(experiment.get("publication_id"))))
    return record


def _content_hash(*collections: Any) -> str:
    digest = hashlib.sha256()
    for coll in collections:
        digest.update(json.dumps(coll, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


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
    diseases_by_id = {str(d["disease_id"]): d for d in diseases}
    organisms_by_id = {str(o["organism_id"]): o for o in organisms}
    publications_by_id = {str(p["publication_id"]): p for p in publications}

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
            "CREATE TABLE association ("
            "ncbi_id INTEGER, experiment_id INTEGER, full_json TEXT)"
        )
        rows = []
        n_with_taxid = 0
        for exp in experiments:
            ncbi_id = _coerce_taxid(exp.get("organism_ncbi_id"))
            if ncbi_id is not None:
                n_with_taxid += 1
            joined = join_record(exp, diseases_by_id, organisms_by_id, publications_by_id)
            rows.append(
                (ncbi_id, int(exp["experiment_id"]), json.dumps(joined, ensure_ascii=False))
            )
        con.executemany("INSERT INTO association VALUES (?, ?, ?)", rows)
        con.execute("CREATE INDEX ix_association_ncbi ON association(ncbi_id)")
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("content_sha256", content),
                ("n_experiments", str(len(experiments))),
                ("n_with_taxid", str(n_with_taxid)),
                ("source", API_BASE),
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
        has_hash = con.execute(
            "SELECT value FROM meta WHERE key = 'content_sha256'"
        ).fetchone()
        count = con.execute("SELECT COUNT(*) FROM association").fetchone()[0]
        return bool(has_hash) and count > 0
    except sqlite3.Error:
        return False
    finally:
        con.close()


def _fetch(endpoint: str) -> list[dict]:
    url = f"{API_BASE}/{endpoint}"
    with urllib.request.urlopen(url, timeout=_FETCH_TIMEOUT) as response:  # noqa: S310 (known host)
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
    ``BackendConfigurationError`` is raised. ``progress`` is accepted for API
    symmetry with ncbi_weaver (the build is fast and currently silent).
    """
    path = Path(db_path) if db_path else default_disbiome_db_path()
    return ensure_local_db(
        path,
        is_valid=db_is_valid,
        build=_build,
        consent_message=_CONSENT_MESSAGE.format(path=path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=200_000_000,  # ~7 MB data; generous headroom for the temp build
    )
