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
import urllib.request
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from braidworks.core.localdb import ProgressCallback, default_db_path, ensure_local_db

API_BASE = "https://gmrepo.humangut.info/api"
NAMESPACE = "gmrepo"
DB_FILENAME = "gmrepo.sqlite"
_FETCH_TIMEOUT = 180  # seconds
_FETCH_WORKERS = 8  # concurrent per-taxon requests (network-bound; polite to the API)
# GMrepo sits behind Cloudflare; send a UA so the POST is not 403'd (cf. agora_weaver).
_USER_AGENT = "braidworks/gmrepo_weaver (+https://github.com/rafaelmdc/braidworks)"

_CONSENT_MESSAGE = (
    "gmrepo_weaver's local DB is not built yet ({path}).\n"
    "It is small (a few MB fetched from the keyless GMrepo API; the build walks every gut "
    "taxon so it takes ~10-20 minutes), but acquisition is opt-in. To build it:\n"
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


def write_db(
    target: Path,
    *,
    overview: list[dict],
    associations: list[dict],
    phenotypes: list[dict],
    sample_profiles: list[dict] | None = None,
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
    sample_profiles = sample_profiles or []
    content = _content_hash(
        sorted(overview, key=lambda r: (int(r["ncbi_taxon_id"]), r.get("rank", ""))),
        sorted(
            associations,
            key=lambda r: (int(r["ncbi_taxon_id"]), str(r.get("mesh_id", ""))),
        ),
        sorted(phenotypes, key=lambda p: str(p.get("mesh_id", ""))),
        sorted(
            sample_profiles,
            key=lambda r: (str(r.get("mesh_id", "")), str(r.get("run_id", "")), int(r["ncbi_taxon_id"])),
        ),
    )

    con = sqlite3.connect(target)
    try:
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.execute(
            "CREATE TABLE overview ("
            "ncbi_taxon_id INTEGER, rank TEXT, name TEXT, "
            "pct_of_all_samples REAL, nr_phenotypes INTEGER, presented_samples INTEGER)"
        )
        con.execute(
            "CREATE TABLE association ("
            "ncbi_taxon_id INTEGER, rank TEXT, mesh_id TEXT, phenotype_name TEXT, "
            "samples INTEGER, phenotype_valid_runs INTEGER, prevalence_percentage REAL, "
            "abundance_mean REAL, abundance_median REAL, abundance_sd REAL)"
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
            "mesh_id TEXT, run_id TEXT, ncbi_taxon_id INTEGER, rank TEXT, relative_abundance REAL)"
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
    """A usable, fully-built GMrepo DB: has the meta hash and non-empty associations."""
    if not path.exists():
        return False
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        has_hash = con.execute("SELECT value FROM meta WHERE key = 'content_sha256'").fetchone()
        assoc = con.execute("SELECT COUNT(*) FROM association").fetchone()[0]
        # A profiles-only build (associations empty) is still usable for the sample_profiles
        # capability, so accept either populated table.
        profiles = con.execute("SELECT COUNT(*) FROM sample_profile").fetchone()[0]
        return bool(has_hash) and (assoc > 0 or profiles > 0)
    except sqlite3.Error:
        return False
    finally:
        con.close()


def _post(endpoint: str, body: dict[str, Any]) -> Any:
    """POST a JSON body to a GMrepo endpoint and return the parsed JSON.

    The endpoint MUST carry a trailing slash: GMrepo's Django runs with
    ``APPEND_SLASH``, which 500s a slash-less POST (it cannot redirect and keep the
    body) — the published example code predates that server config.
    """
    request = urllib.request.Request(  # noqa: S310 (known host)
        f"{API_BASE}/{endpoint}/",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:  # noqa: S310
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
    rows = payload.get("phenotypes_associated_with_taxon", []) if isinstance(payload, dict) else []
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
    post: Callable[[str, dict[str, Any]], Any], mesh_id: str, max_runs: int
) -> list[str]:
    """List up to ``max_runs`` run ids for a phenotype (paginated over the live *Limit route)."""
    run_ids: list[str] = []
    skip = 0
    while len(run_ids) < max_runs:
        want = min(_RUNS_PAGE, max_runs - len(run_ids))
        batch = post(_RUNS_ENDPOINT, {"mesh_id": mesh_id, "skip": skip, "limit": want})
        rows = batch if isinstance(batch, list) else _rows_of(batch, "runs")
        if not rows:
            break
        for r in rows:
            rid = r.get("run_id") if isinstance(r, dict) else None
            if rid:
                run_ids.append(str(rid))
        skip += len(rows)
        if len(rows) < want:
            break
    return run_ids[:max_runs]


def _run_profile_rows(mesh_id: str, run_id: str, payload: Any) -> list[dict]:
    """Rows of ``getFullTaxonomicProfileByRunID`` → per-(run, taxon) relative-abundance dicts."""
    if not isinstance(payload, dict):
        return []
    out: list[dict] = []
    for rank_key in ("species", "genus"):
        for row in payload.get(rank_key, []) or []:
            if not isinstance(row, dict):
                continue
            taxid = _coerce_taxid(row.get("ncbi_taxon_id"))
            abundance = _num(row.get("relative_abundance"))
            if taxid is None or abundance is None:
                continue
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
) -> list[dict]:
    """Fetch per-run species/genus profiles for the given phenotypes (bounded by ``max_runs``).

    One run-listing walk per phenotype, then the per-run profiles over the thread pool
    (network-bound). A flaky run is skipped so it can't sink the crawl.
    """
    profiles: list[dict] = []
    for mesh_id in mesh_ids:
        run_ids = _fetch_run_ids(post, mesh_id, max_runs)

        def _one(run_id: str, mesh_id: str = mesh_id) -> list[dict]:
            try:
                return _run_profile_rows(mesh_id, run_id, post(_PROFILE_ENDPOINT, {"run_id": run_id}))
            except Exception:  # noqa: BLE001 — one flaky run must not sink the crawl
                return []

        with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
            futures = {pool.submit(_one, rid): rid for rid in run_ids}
            for done, future in enumerate(as_completed(futures), start=1):
                if progress:
                    progress(done, len(run_ids), f"{mesh_id} run {futures[future]}")
                profiles.extend(future.result())
    return profiles


def _fetch_tables(
    post: Callable[[str, dict[str, Any]], Any],
    progress: ProgressCallback | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Fetch (overview, associations, phenotypes) from GMrepo via ``post`` (injectable).

    One call each for the taxon universe (``get_all_gut_microbes``) and the phenotype
    catalog (``get_all_phenotypes``), then one call per overview taxon for its
    per-phenotype abundance rows — those ~3000 calls are pure network wait, so they run
    over a small thread pool (``_FETCH_WORKERS``) to keep the one-time build to minutes
    rather than hours. A per-taxon fetch that errors is skipped (a partial taxon must not
    abort the build); the taxon still keeps its overview row.
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
            return _taxon_associations(taxid, post(_TAXON_ENDPOINT, {"ncbi_taxon_id": taxid}))
        except Exception:  # noqa: BLE001 — a single flaky taxon must not sink the build
            return []

    associations: list[dict] = []
    total = len(overview)
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        futures = {pool.submit(_one, t["ncbi_taxon_id"]): t["ncbi_taxon_id"] for t in overview}
        for done, future in enumerate(as_completed(futures), start=1):
            if progress:
                progress(done, total, f"taxon {futures[future]}")
            associations.extend(future.result())
    return overview, associations, phenotypes


def _build(
    target: Path,
    *,
    post: Callable[[str, dict[str, Any]], Any] = _post,
    progress: ProgressCallback | None = None,
    profile_phenotypes: list[str] | None = None,
    profile_max_runs: int = 200,
) -> None:
    """Fetch the GMrepo tables and write the SQLite at ``target`` (``post`` injectable).

    If ``profile_phenotypes`` (mesh ids) are given, also crawl up to ``profile_max_runs``
    per-run profiles for each — the per-sample substrate for the co-occurrence layer.
    """
    overview, associations, phenotypes = _fetch_tables(post, progress)
    sample_profiles = (
        _fetch_profiles(post, profile_phenotypes, profile_max_runs, progress)
        if profile_phenotypes
        else []
    )
    write_db(
        target,
        overview=overview,
        associations=associations,
        phenotypes=phenotypes,
        sample_profiles=sample_profiles,
    )


def ensure_gmrepo_db(
    db_path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    progress: ProgressCallback | None = None,
    profile_phenotypes: list[str] | None = None,
    profile_max_runs: int = 200,
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
            "ORDER BY ncbi_taxon_id, mesh_id"
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
