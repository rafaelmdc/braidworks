"""Local GMrepo DB acquisition: fetch the keyless abundance tables once and build a
small SQLite the ``local`` backend serves offline.

GMrepo has no bulk dump, but its POST-JSON API exposes the whole per-taxon /
per-phenotype abundance summary in a bounded set of calls (a few MB total), so
"download" here means walking these endpoints:

- ``/api/get_all_gut_microbes`` (once) — every species/genus's *global* gut-metagenome
  presence: percent of all samples it occurs in and how many phenotypes it appears in.
  A disease-agnostic ecology summary → the ``overview`` table (also the taxon universe).
- ``/api/get_all_phenotypes`` (once) — the phenotype catalog (mesh id ``disease`` + name
  ``term``).
- ``/api/getPhenotypesAndAbundanceSummaryOfAAssociatedTaxon`` (once per overview taxon) —
  that taxon's per-phenotype rows: sample count, and relative-abundance mean/median/sd
  within the phenotype → the ``association`` table. (GMrepo's older ``*ByMeshID`` endpoints
  now return empty; this taxon-centric one is the live route, and it is keyed on exactly
  the ``ncbi_taxon_id`` the weaver consumes.)

The generic acquisition plumbing (consent gate, cross-process lock, disk precheck,
atomic publish) lives in ``braidworks.core.localdb``; this module supplies only the
domain pieces — ``db_is_valid`` and ``_build`` — plus the POST fetch and the join.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from braidworks.core.localdb import ProgressCallback, default_db_path, ensure_local_db

from gmrepo_weaver.acquisition import AcquisitionPolicy, _AcquisitionClient, _map_workers

API_BASE = "https://gmrepo.humangut.info/api"
NAMESPACE = "gmrepo"
DB_FILENAME = "gmrepo.sqlite"
_FETCH_TIMEOUT = 180  # seconds
_FETCH_WORKERS = 4  # bounded tasks; request spacing is enforced separately
# GMrepo sits behind Cloudflare; send a UA so the POST is not 403'd (cf. agora_weaver).
_USER_AGENT = "braidworks/gmrepo_weaver (+https://github.com/rafaelmdc/braidworks)"

_CONSENT_MESSAGE = (
    "gmrepo_weaver's local DB is not built yet ({path}).\n"
    "It is small (a few MB fetched from the keyless GMrepo API; the build walks every gut "
    "taxon using thousands of requests; duration depends on the acquisition policy), "
    "but acquisition is opt-in. To build it:\n"
    "  - call build_gmrepo_weaver_configured(auto_setup=True), or\n"
    "  - set BRAIDWORKS_AUTO_DOWNLOAD=1, or\n"
    "  - call gmrepo_weaver.setup.ensure_gmrepo_db(auto=True).\n"
    "Override the location with db_path=... or the BRAIDWORKS_DATA_DIR env var."
)


def default_gmrepo_db_path() -> Path:
    """Per-user default DB path (override via ``BRAIDWORKS_DATA_DIR``)."""
    return default_db_path(NAMESPACE, DB_FILENAME)


def _coerce_taxid(value: Any) -> int | None:
    """Coerce an ``ncbi_taxon_id`` (int or digit-string) to int, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _num(value: Any) -> float | None:
    """Coerce an abundance/prevalence field to float, tolerating strings and None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    """Coerce a count field to int, tolerating strings and None."""
    num = _num(value)
    return None if num is None else int(num)


class _InvalidResponse(ValueError):
    """A source response cannot establish acquisition coverage."""


_EXPECTED_FAILURES = (
    urllib.error.URLError,
    OSError,
    json.JSONDecodeError,
    UnicodeDecodeError,
    _InvalidResponse,
)


def _rows_of(payload: Any, *keys: str) -> list[dict]:
    """Normalize an endpoint payload to a list of row dicts.

    GMrepo returns either a bare JSON array of rows or an object wrapping the array
    under a known key (e.g. ``{"phenotypes": [...]}``, ``{"all_species": [...]}``).
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def _content_hash(*collections: Any) -> str:
    digest = hashlib.sha256()
    for coll in collections:
        digest.update(json.dumps(coll, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


def _distinct_rows(rows: list[dict], identity: tuple[str, ...]) -> list[dict]:
    """Collapse exact duplicate identities, rejecting contradictory measurements."""
    distinct: dict[tuple, dict] = {}
    for source in rows:
        row = dict(source)
        if "rank" in identity:
            row["rank"] = str(row.get("rank") or "")
        if "ncbi_taxon_id" in identity:
            row["ncbi_taxon_id"] = int(row["ncbi_taxon_id"])
        key = tuple(row.get(field) for field in identity)
        if any(
            value is None or (value == "" and field != "rank")
            for field, value in zip(identity, key)
        ):
            raise ValueError(f"GMrepo row lacks logical identity {identity}")
        if key in distinct and distinct[key] != row:
            raise ValueError(f"Conflicting GMrepo rows for {identity}: {key}")
        distinct[key] = row
    return [distinct[key] for key in sorted(distinct)]


def write_db(
    target: Path,
    *,
    overview: list[dict],
    associations: list[dict],
    phenotypes: list[dict],
    sample_profiles: list[dict] | None = None,
    acquisition: dict[str, Any] | None = None,
) -> None:
    """Build the SQLite at ``target`` from already-fetched (or canned) tables.

    Shared by the live build (``_build``) and the fixture, so schema + join live in
    one place. ``overview`` rows are one-per-taxon (normalized global summary);
    ``association`` rows are one-per-(taxon, phenotype). ``ncbi_taxon_id`` is the join
    key the backend queries on for the taxon-centric capability.

    ``sample_profiles`` (optional) are one-per-(phenotype, run, taxon) relative-abundance
    rows for the *per-sample* capability (``gmrepo.sample_profiles``, keyed on ``mesh_id``)
    that feeds the co-occurrence layer. Empty by default so the taxon-abundance build stays
    the fast few-MB crawl; populated only when a caller asks for specific phenotypes' runs.
    """
    overview = _distinct_rows(overview, ("ncbi_taxon_id", "rank"))
    associations = _distinct_rows(associations, ("ncbi_taxon_id", "rank", "mesh_id"))
    phenotypes = _distinct_rows(phenotypes, ("mesh_id",))
    sample_profiles = _distinct_rows(
        sample_profiles or [], ("mesh_id", "run_id", "ncbi_taxon_id", "rank")
    )
    acquisition = acquisition or {"scope": "caller-supplied", "taxa": {}, "profiles": {}}
    content = _content_hash(
        acquisition,
        sorted(overview, key=lambda r: (int(r["ncbi_taxon_id"]), r.get("rank", ""))),
        sorted(
            associations,
            key=lambda r: (int(r["ncbi_taxon_id"]), str(r.get("mesh_id", ""))),
        ),
        sorted(phenotypes, key=lambda p: str(p.get("mesh_id", ""))),
        sorted(
            sample_profiles,
            key=lambda r: (
                str(r.get("mesh_id", "")),
                str(r.get("run_id", "")),
                int(r["ncbi_taxon_id"]),
            ),
        ),
    )

    con = sqlite3.connect(target)
    try:
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.execute(
            "CREATE TABLE overview ("
            "ncbi_taxon_id INTEGER NOT NULL, rank TEXT NOT NULL, name TEXT, "
            "pct_of_all_samples REAL, nr_phenotypes INTEGER, presented_samples INTEGER, "
            "PRIMARY KEY (ncbi_taxon_id, rank))"
        )
        con.execute(
            "CREATE TABLE association ("
            "ncbi_taxon_id INTEGER NOT NULL, rank TEXT NOT NULL, mesh_id TEXT NOT NULL, phenotype_name TEXT, "
            "samples INTEGER, phenotype_valid_runs INTEGER, prevalence_percentage REAL, "
            "abundance_mean REAL, abundance_median REAL, abundance_sd REAL, "
            "PRIMARY KEY (ncbi_taxon_id, rank, mesh_id))"
        )
        con.executemany(
            "INSERT INTO overview VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    int(r["ncbi_taxon_id"]),
                    r.get("rank"),
                    r.get("name"),
                    _num(r.get("pct_of_all_samples")),
                    _int(r.get("nr_phenotypes")),
                    _int(r.get("presented_samples")),
                )
                for r in overview
            ],
        )
        con.executemany(
            "INSERT INTO association VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    int(r["ncbi_taxon_id"]),
                    r.get("rank"),
                    r.get("mesh_id"),
                    r.get("phenotype_name"),
                    _int(r.get("samples")),
                    _int(r.get("phenotype_valid_runs")),
                    _num(r.get("prevalence_percentage")),
                    _num(r.get("abundance_mean")),
                    _num(r.get("abundance_median")),
                    _num(r.get("abundance_sd")),
                )
                for r in associations
            ],
        )
        con.execute(
            "CREATE TABLE sample_profile ("
            "mesh_id TEXT NOT NULL, run_id TEXT NOT NULL, ncbi_taxon_id INTEGER NOT NULL, "
            "rank TEXT NOT NULL, relative_abundance REAL, "
            "PRIMARY KEY (mesh_id, run_id, ncbi_taxon_id, rank))"
        )
        con.executemany(
            "INSERT INTO sample_profile VALUES (?, ?, ?, ?, ?)",
            [
                (
                    r.get("mesh_id"),
                    r.get("run_id"),
                    int(r["ncbi_taxon_id"]),
                    r.get("rank"),
                    _num(r.get("relative_abundance")),
                )
                for r in sample_profiles
            ],
        )
        con.execute("CREATE INDEX ix_overview_taxon ON overview(ncbi_taxon_id)")
        con.execute("CREATE INDEX ix_association_taxon ON association(ncbi_taxon_id)")
        con.execute("CREATE INDEX ix_profile_mesh ON sample_profile(mesh_id)")
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("schema_version", "3"),
                ("acquisition", json.dumps(acquisition, sort_keys=True)),
                ("build_id", uuid.uuid4().hex),
                ("content_sha256", content),
                ("n_overview", str(len(overview))),
                ("n_associations", str(len(associations))),
                ("n_phenotypes", str(len(phenotypes))),
                ("n_sample_profiles", str(len(sample_profiles))),
                ("source", API_BASE),
            ],
        )
        con.commit()
    finally:
        con.close()


def db_is_valid(path: Path) -> bool:
    """A built GMrepo resource with source identity, query tables and acquisition outcomes."""
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
        for table, expected in (
            ("overview", ["ncbi_taxon_id", "rank"]),
            ("association", ["ncbi_taxon_id", "rank", "mesh_id"]),
            ("sample_profile", ["mesh_id", "run_id", "ncbi_taxon_id", "rank"]),
        ):
            columns = con.execute(f"PRAGMA table_info({table})").fetchall()
            primary = [
                column[1] for column in sorted(columns, key=lambda column: column[5]) if column[5]
            ]
            if primary != expected:
                return False
        has_hash = con.execute("SELECT value FROM meta WHERE key = 'content_sha256'").fetchone()
        assoc = con.execute("SELECT COUNT(*) FROM association").fetchone()[0]
        # A profiles-only build (associations empty) is still usable for the sample_profiles
        # capability, so accept either populated table.
        profiles = con.execute("SELECT COUNT(*) FROM sample_profile").fetchone()[0]
        manifest = con.execute("SELECT value FROM meta WHERE key = 'acquisition'").fetchone()
        return bool(
            has_hash
            and manifest
            and (
                assoc > 0
                or profiles > 0
                or con.execute("SELECT 1 FROM overview LIMIT 1").fetchone()
                or json.loads(manifest[0]).get("profiles")
            )
        )
    except (sqlite3.Error, json.JSONDecodeError, TypeError):
        return False
    finally:
        con.close()


def _post(endpoint: str, body: dict[str, Any]) -> Any:
    """POST a JSON body to a GMrepo endpoint and return the parsed JSON.

    The endpoint MUST carry a trailing slash: GMrepo's Django runs with
    ``APPEND_SLASH``, which 500s a slash-less POST (it cannot redirect and keep the
    body) — the published example code predates that server config.
    """
    request = urllib.request.Request(
        f"{API_BASE}/{endpoint}/",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


_TAXON_ENDPOINT = "getPhenotypesAndAbundanceSummaryOfAAssociatedTaxon"
# Per-run endpoints for the sample-profile crawl (the co-occurrence substrate). The
# ``*Limit`` run-listing route is the live one — the plain getAssociatedRunsByPhenotypeMeshID
# returns empty (same dead family as the *ByMeshID abundance endpoints).
_RUNS_ENDPOINT = "getAssociatedRunsByPhenotypeMeshIDLimit"
_PROFILE_ENDPOINT = "getFullTaxonomicProfileByRunID"
_RUNS_PAGE = 100  # run-listing pagination page size


def _overview_rows(gut_microbes: Any) -> list[dict]:
    """Normalize ``get_all_gut_microbes`` into per-taxon overview rows (both ranks)."""
    rows: list[dict] = []
    for rank, key in (("genus", "all_genus"), ("species", "all_species")):
        for row in _rows_of(gut_microbes, key):
            taxid = _coerce_taxid(row.get("ncbi_taxon_id"))
            if taxid is None:
                continue
            rows.append(
                {
                    "ncbi_taxon_id": taxid,
                    "rank": rank,
                    "name": row.get("name"),
                    "pct_of_all_samples": row.get("pct_of_all_samples"),
                    "nr_phenotypes": row.get("nr_phenotypes"),
                    "presented_samples": row.get("presented_samples"),
                }
            )
    return rows


def _prevalence(samples: Any, valid_runs: Any) -> float | None:
    """Percent of a phenotype's valid runs in which this taxon is present."""
    s, v = _int(samples), _int(valid_runs)
    if s is None or not v:
        return None
    return round(100.0 * s / v, 4)


def _taxon_associations(taxid: int, payload: Any) -> list[dict]:
    """Rows of ``getPhenotypesAndAbundanceSummaryOfAAssociatedTaxon`` → association dicts."""
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("phenotypes_associated_with_taxon"), list)
        or any(not isinstance(row, dict) for row in payload["phenotypes_associated_with_taxon"])
    ):
        raise _InvalidResponse("taxon associations must contain a valid row list")
    rows = payload["phenotypes_associated_with_taxon"]
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "ncbi_taxon_id": taxid,
                "rank": row.get("taxon_rank_level"),
                "mesh_id": row.get("disease"),
                "phenotype_name": row.get("term"),
                "samples": row.get("samples"),
                "phenotype_valid_runs": row.get("valid_runs"),
                "prevalence_percentage": _prevalence(row.get("samples"), row.get("valid_runs")),
                "abundance_mean": row.get("abus_mean"),
                "abundance_median": row.get("abus_median"),
                "abundance_sd": row.get("abus_sd"),
            }
        )
    return out


def _fetch_run_ids(
    post: Callable[[str, dict[str, Any]], Any],
    mesh_id: str,
    max_runs: int,
    coverage: dict[str, Any] | None = None,
) -> list[str]:
    """List up to ``max_runs`` run ids for a phenotype (paginated over the live *Limit route)."""
    if isinstance(max_runs, bool) or not isinstance(max_runs, int) or max_runs < 1:
        raise ValueError("max_runs must be a positive integer")
    run_ids: list[str] = []
    seen: set[str] = set()
    exhausted = False
    skip = 0
    while len(run_ids) < max_runs:
        want = min(_RUNS_PAGE, max_runs - len(run_ids))
        batch = post(_RUNS_ENDPOINT, {"mesh_id": mesh_id, "skip": skip, "limit": want})
        rows = (
            batch
            if isinstance(batch, list)
            else batch.get("runs")
            if isinstance(batch, dict)
            else None
        )
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise _InvalidResponse("run listing must contain a row list")
        if not rows:
            exhausted = True
            break
        for r in rows:
            rid = r.get("run_id") if isinstance(r, dict) else None
            if not rid or str(rid) in seen:
                raise _InvalidResponse("run listing contains a missing/repeated run id")
            seen.add(str(rid))
            run_ids.append(str(rid))
        skip += len(rows)
        if len(rows) < want:
            exhausted = True
            break
    if coverage is not None:
        coverage.update(
            {
                "selected_runs": len(run_ids[:max_runs]),
                "cap": max_runs,
                "listing_exhausted": exhausted,
                "capped": not exhausted,
            }
        )
    return run_ids[:max_runs]


def _run_profile_rows(mesh_id: str, run_id: str, payload: Any) -> list[dict]:
    """Rows of ``getFullTaxonomicProfileByRunID`` → per-(run, taxon) relative-abundance dicts."""
    if (
        not isinstance(payload, dict)
        or not any(key in payload for key in ("species", "genus"))
        or any(not isinstance(payload.get(key, []), list) for key in ("species", "genus"))
    ):
        raise _InvalidResponse("run profile must contain species/genus row lists")
    out: list[dict] = []
    for rank_key in ("species", "genus"):
        for row in payload.get(rank_key, []) or []:
            if not isinstance(row, dict):
                raise _InvalidResponse("run profile row must be an object")
            taxid = _coerce_taxid(row.get("ncbi_taxon_id"))
            abundance = _num(row.get("relative_abundance"))
            if taxid is None or abundance is None:
                raise _InvalidResponse("run profile row lacks taxon/abundance")
            out.append(
                {
                    "mesh_id": mesh_id,
                    "run_id": run_id,
                    "ncbi_taxon_id": taxid,
                    "rank": row.get("taxon_rank_level") or rank_key,
                    "relative_abundance": abundance,
                }
            )
    return out


def _fetch_profiles(
    post: Callable[[str, dict[str, Any]], Any],
    mesh_ids: list[str],
    max_runs: int,
    progress: ProgressCallback | None = None,
    coverage: dict[str, Any] | None = None,
    *,
    workers: int = _FETCH_WORKERS,
) -> list[dict]:
    """Fetch per-run species/genus profiles for the given phenotypes (bounded by ``max_runs``).

    One run-listing walk per phenotype, then the per-run profiles over the thread pool
    (network-bound). Expected failures are recorded separately from empty profiles.
    """
    profiles: list[dict] = []
    fetched_runs: dict[str, tuple[list[dict], dict[str, Any]]] = {}
    for mesh_id in dict.fromkeys(mesh_ids):
        scope: dict[str, Any] = {
            "requested": True,
            "cap": max_runs,
            "runs": {},
            "selected_runs": 0,
            "requested_runs": 0,
            "fetched_runs": 0,
            "empty_runs": 0,
            "failed_runs": 0,
            "cohort_total_runs": None,
        }
        if coverage is not None:
            coverage[mesh_id] = scope
        try:
            run_ids = _fetch_run_ids(post, mesh_id, max_runs, scope)
        except _EXPECTED_FAILURES as exc:
            scope.update({"status": "failed", "complete": False, "error": str(exc)})
            continue

        scope["requested_runs"] = len(run_ids)

        def _one(run_id: str, mesh_id: str = mesh_id):
            if run_id in fetched_runs:
                rows, outcome = fetched_runs[run_id]
                return [{**row, "mesh_id": mesh_id} for row in rows], dict(outcome)
            try:
                rows = _run_profile_rows(
                    mesh_id, run_id, post(_PROFILE_ENDPOINT, {"run_id": run_id})
                )
                return rows, {"status": "fetched" if rows else "empty", "rows": len(rows)}
            except _EXPECTED_FAILURES as exc:
                return [], {"status": "failed", "error": str(exc)}

        for done, (run_id, (rows, outcome)) in enumerate(
            _map_workers(run_ids, _one, workers=workers), start=1
        ):
            if progress:
                progress(done, len(run_ids), f"{mesh_id} run {run_id}")
            fetched_runs[run_id] = (rows, outcome)
            scope["runs"][run_id] = outcome
            profiles.extend(rows)
        statuses = [outcome["status"] for outcome in scope["runs"].values()]
        scope.update(
            {
                "status": "acquired",
                "fetched_runs": len(statuses) - statuses.count("failed"),
                "empty_runs": statuses.count("empty"),
                "failed_runs": statuses.count("failed"),
                "complete": scope["listing_exhausted"] and "failed" not in statuses,
            }
        )
    return profiles


def _fetch_tables(
    post: Callable[[str, dict[str, Any]], Any],
    progress: ProgressCallback | None = None,
    coverage: dict[str, Any] | None = None,
    *,
    workers: int = _FETCH_WORKERS,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Fetch (overview, associations, phenotypes) from GMrepo via ``post`` (injectable).

    One call each for the taxon universe (``get_all_gut_microbes``) and the phenotype
    catalog (``get_all_phenotypes``), then one call per overview taxon for its
    per-phenotype abundance rows — those ~3000 calls are pure network wait, so they run
    over a small thread pool (``_FETCH_WORKERS``) to keep the one-time build to minutes
    rather than hours. Expected per-taxon failures retain their acquisition outcome
    alongside the overview row; programming faults propagate.
    """
    overview = _overview_rows(post("get_all_gut_microbes", {}))

    phenotypes = [
        {
            "mesh_id": p.get("disease"),
            "phenotype_name": p.get("term"),
            "valid_runs": p.get("valid_runs"),
        }
        for p in _rows_of(post("get_all_phenotypes", {}), "phenotypes")
        if p.get("disease")
    ]

    def _one(taxid: int) -> list[dict]:
        try:
            rows = _taxon_associations(taxid, post(_TAXON_ENDPOINT, {"ncbi_taxon_id": taxid}))
            return rows, {
                "status": "fetched" if rows else "empty",
                "complete": True,
                "rows": len(rows),
            }
        except _EXPECTED_FAILURES as exc:
            return [], {"status": "failed", "complete": False, "error": str(exc)}

    associations: list[dict] = []
    distinct = list(dict.fromkeys(t["ncbi_taxon_id"] for t in overview))
    total = len(distinct)
    for done, (taxid, (rows, outcome)) in enumerate(
        _map_workers(distinct, _one, workers=workers), start=1
    ):
        if progress:
            progress(done, total, f"taxon {taxid}")
        if coverage is not None:
            coverage[str(taxid)] = outcome
        associations.extend(rows)
    return overview, associations, phenotypes


def _build(
    target: Path,
    *,
    post: Callable[[str, dict[str, Any]], Any] = _post,
    progress: ProgressCallback | None = None,
    profile_phenotypes: list[str] | None = None,
    profile_max_runs: int = 200,
    acquisition_policy: AcquisitionPolicy | None = None,
) -> None:
    """Fetch the GMrepo tables and write the SQLite at ``target`` (``post`` injectable).

    If ``profile_phenotypes`` (mesh ids) are given, also crawl up to ``profile_max_runs``
    per-run profiles for each — the per-sample substrate for the co-occurrence layer.
    """
    policy = acquisition_policy or AcquisitionPolicy()
    client = _AcquisitionClient(post, policy)
    acquisition: dict[str, Any] = {"scope": "gmrepo-api", "taxa": {}, "profiles": {}}
    overview, associations, phenotypes = _fetch_tables(
        client, progress, acquisition["taxa"], workers=policy.workers
    )
    sample_profiles = (
        _fetch_profiles(
            client,
            profile_phenotypes,
            profile_max_runs,
            progress,
            acquisition["profiles"],
            workers=policy.workers,
        )
        if profile_phenotypes
        else []
    )
    for phenotype in phenotypes:
        if phenotype["mesh_id"] in acquisition["profiles"]:
            acquisition["profiles"][phenotype["mesh_id"]]["cohort_total_runs"] = phenotype[
                "valid_runs"
            ]
    acquisition["requests"] = client.coverage()
    write_db(
        target,
        overview=overview,
        associations=associations,
        phenotypes=phenotypes,
        sample_profiles=sample_profiles,
        acquisition=acquisition,
    )


def ensure_gmrepo_db(
    db_path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    progress: ProgressCallback | None = None,
    profile_phenotypes: list[str] | None = None,
    profile_max_runs: int = 200,
    acquisition_policy: AcquisitionPolicy | None = None,
) -> Path:
    """Ensure a valid local GMrepo SQLite exists, building it if consented.

    Idempotent: a valid DB is returned instantly. Otherwise acquisition needs consent
    (``auto`` or ``BRAIDWORKS_AUTO_DOWNLOAD``); without it, an actionable
    ``BackendConfigurationError`` is raised. ``refresh=True`` rebuilds from the API.

    ``profile_phenotypes`` (mesh ids) additionally crawl per-run sample profiles for the
    co-occurrence layer; because the DB build is idempotent, adding profiles to an existing
    DB requires ``refresh=True`` (the profiles ride along with a full rebuild).
    """
    path = Path(db_path) if db_path else default_gmrepo_db_path()

    def _build_with_progress(target: Path) -> None:
        _build(
            target,
            progress=progress,
            profile_phenotypes=profile_phenotypes,
            profile_max_runs=profile_max_runs,
            acquisition_policy=acquisition_policy,
        )

    return ensure_local_db(
        path,
        is_valid=db_is_valid,
        build=_build_with_progress,
        consent_message=_CONSENT_MESSAGE.format(path=path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=500_000_000,  # a few MB of data; generous headroom for the temp build
    )


def iter_abundances(
    db_path: str | Path | None = None, *, auto: bool = False
) -> Iterator[dict[str, Any]]:
    """Yield every GMrepo per-(taxon, phenotype) abundance row — the bulk view.

    The ``fetch`` capability answers "this microbe's abundances" per taxid; this is its
    bulk counterpart, for an ingestion that needs the *whole* table (e.g. to seed an
    abundance feature block or compare GMrepo prevalence to Disbiome's presence-only
    truth over all taxa). Ensures the local DB (consent-gated), then streams::

        {taxid, rank, mesh_id, phenotype_name, samples, prevalence_percentage, abundance_median}
    """
    path = ensure_gmrepo_db(db_path, auto=auto)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        cursor = con.execute(
            "SELECT ncbi_taxon_id, rank, mesh_id, phenotype_name, samples, "
            "prevalence_percentage, abundance_median FROM association "
            "ORDER BY ncbi_taxon_id, mesh_id, rank"
        )
        for taxid, rank, mesh_id, phenotype_name, samples, prevalence, median in cursor:
            yield {
                "taxid": int(taxid),
                "rank": rank,
                "mesh_id": mesh_id,
                "phenotype_name": phenotype_name,
                "samples": samples,
                "prevalence_percentage": prevalence,
                "abundance_median": median,
            }
    finally:
        con.close()
