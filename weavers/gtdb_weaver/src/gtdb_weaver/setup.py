"""ensure_gtdb_db — acquiring the local NCBI→GTDB crosswalk (gtdb_weaver-specific).

The generic mechanics — consent gate, streamed download, disk precheck, build lock,
atomic publish — live in ``braidworks.core.localdb``. This module supplies only the
GTDB specifics: the metadata source URLs (bac120 + ar53), what makes a built DB
*valid*, and the build itself (stream the gzipped metadata TSVs → the small crosswalk
SQLite via ``taxonomy.build_crosswalk_db``, recording the GTDB release).

Interactive entry points obtain consent by prompting, then call this with ``auto=True``.
This function never prompts, so it stays deterministic and easy to test.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import logging
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import closing
from itertools import chain
from pathlib import Path

from braidworks.core.localdb import auto_consented, ensure_local_db
from braidworks.core.localdb import default_db_path as _core_default_db_path
from braidworks.core.localdb import download as _download

from gtdb_weaver import taxonomy
from gtdb_weaver.releases import (
    DEFAULT_RELEASE,
    file_hash,
    release_bundle,
    release_sources,
    verify_resource,
)
from gtdb_weaver.tree import NewickError, parse_newick

logger = logging.getLogger("gtdb_weaver.setup")

_SOURCES = release_sources(DEFAULT_RELEASE)
DEFAULT_BAC120_URL = _SOURCES["bac120"]
DEFAULT_AR53_URL = _SOURCES["ar53"]
DEFAULT_BAC120_TREE_URL = _SOURCES["bac120_tree"]
DEFAULT_AR53_TREE_URL = _SOURCES["ar53_tree"]

_NAMESPACE = "gtdb"
_DB_FILENAME = "gtdb_crosswalk.sqlite"
# Two gzipped metadata TSVs (~283 MB for R232 combined) streamed, plus a small SQLite; a
# modest margin covers the temporary downloads and the build.
_MIN_FREE_BYTES = 2 * 1024**3

__all__ = [
    "DEFAULT_AR53_TREE_URL",
    "DEFAULT_AR53_URL",
    "DEFAULT_BAC120_TREE_URL",
    "DEFAULT_BAC120_URL",
    "auto_consented",
    "db_is_valid",
    "default_db_path",
    "default_tree_paths",
    "ensure_gtdb_db",
    "ensure_gtdb_trees",
]


def default_db_path() -> Path:
    """Per-user default crosswalk DB path (``BRAIDWORKS_DATA_DIR`` overrides the cache dir)."""
    return _core_default_db_path(_NAMESPACE, _DB_FILENAME)


def default_tree_paths(release: str = DEFAULT_RELEASE) -> list[Path]:
    """Per-user default reference-tree paths (bac120, ar53), beside the crosswalk DB."""
    sources = release_sources(release)
    parent = default_db_path().parent / (
        "R" + release_sources(release)["bac120"].split("release")[-1].split("/")[0]
    )
    return [parent / sources[label].rsplit("/", 1)[1] for label in ("bac120_tree", "ar53_tree")]


def ensure_gtdb_trees(
    *,
    auto: bool = False,
    refresh: bool = False,
    urls: tuple[str, str] | None = None,
    release: str = DEFAULT_RELEASE,
    bundle: dict | None = None,
) -> list[Path]:
    """Acquire checksum-verified reference trees from the crosswalk's pinned release."""
    descriptor = bundle or release_bundle(release)
    expected_urls = tuple(
        descriptor["resources"][label]["url"] for label in ("bac120_tree", "ar53_tree")
    )
    if urls is not None and urls != expected_urls:
        raise ValueError(
            "custom tree URLs require explicit local tree_paths; do not label them as an official release"
        )
    out = []
    for target, label in zip(
        default_tree_paths(descriptor["release"]), ("bac120_tree", "ar53_tree")
    ):
        resource = descriptor["resources"][label]

        def valid(path, resource=resource):
            try:
                if not path.is_file() or file_hash(path, "md5") != resource["md5"]:
                    return False
                parse_newick(path.read_text())
                return True
            except (OSError, UnicodeDecodeError, NewickError):
                return False

        def build(dest, resource=resource):
            _download(resource["url"], dest, label="Downloading pinned GTDB tree")
            verify_resource(dest, resource)
            parse_newick(dest.read_text())

        ensure_local_db(
            target,
            is_valid=valid,
            build=build,
            consent_message=f"GTDB {descriptor['release']} tree needed at {target}; enable auto_setup to acquire it",
            auto=auto,
            refresh=refresh,
            min_free_bytes=_MIN_FREE_BYTES,
        )
        out.append(target)
    return out


def db_is_valid(path: Path) -> bool:
    """Return whether ``path`` is a readable, populated crosswalk DB."""
    return taxonomy.crosswalk_is_valid(path)


def _consent_message(db_path: Path) -> str:
    return (
        f"GTDB crosswalk database not found at {db_path}.\n"
        "The local backend needs a SQLite NCBI→GTDB crosswalk (~tens of MB, built by\n"
        "streaming the GTDB metadata TSVs, ~283 MB for R232 download). To create it:\n"
        "  - call: build_gtdb_weaver(auto_setup=True)\n"
        "  - or set: BRAIDWORKS_AUTO_DOWNLOAD=1\n"
        "Or build it yourself and pass db_path= to build_gtdb_weaver()."
    )


def _iter_metadata_rows(gz_path: Path) -> Iterator[tuple[int, str, bool, str]]:
    """Stream ``(ncbi_taxid, gtdb_taxonomy, is_rep, accession)`` from a gzipped metadata TSV.

    Columns are located by header name (their ordinal positions drift across releases).
    ``accession`` is the genome id GTDB labels its reference-tree leaves with — kept so a
    species representative can be joined to its leaf. Rows without an integer taxid or a
    taxonomy are skipped.
    """
    with gzip.open(gz_path, mode="rt", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader, None)
        if not header:
            return
        idx = {name: i for i, name in enumerate(header)}
        try:
            c_taxid = idx["ncbi_taxid"]
            c_tax = idx["gtdb_taxonomy"]
            c_rep = idx["gtdb_representative"]
            c_acc = idx["accession"]
        except KeyError as exc:
            raise ValueError(f"GTDB metadata missing expected column {exc}") from exc
        width = max(c_taxid, c_tax, c_rep, c_acc) + 1
        for row in reader:
            if len(row) < width:
                continue
            raw_taxid = row[c_taxid].strip()
            taxonomy_str = row[c_tax].strip()
            if not taxonomy_str:
                continue
            try:
                taxid = int(raw_taxid)
            except ValueError:
                continue
            is_rep = row[c_rep].strip().lower() in {"t", "true", "1"}
            yield taxid, taxonomy_str, is_rep, row[c_acc].strip()


def _build_crosswalk(tmp_db: Path, *, bac120_url: str, ar53_url: str, release: str | None) -> None:
    """Build from one official bundle, or honest custom-content provenance."""
    official = (bac120_url, ar53_url) == (DEFAULT_BAC120_URL, DEFAULT_AR53_URL)
    if official:
        bundle = release_bundle(release or DEFAULT_RELEASE)
    else:
        if (bac120_url == DEFAULT_BAC120_URL) != (ar53_url == DEFAULT_AR53_URL):
            raise ValueError("GTDB custom bundles must supply both metadata URLs")
        bundle = {
            "kind": "custom-content",
            "declared_release": release,
            "resources": {"bac120": {"url": bac120_url}, "ar53": {"url": ar53_url}},
        }
    with tempfile.TemporaryDirectory(dir=tmp_db.parent, prefix="gtdb-sources-") as directory:
        archives = []
        for label in ("bac120", "ar53"):
            resource = bundle["resources"][label]
            archive = Path(directory) / f"{label}.tsv.gz"
            _download(resource["url"], archive, label=f"Downloading GTDB {label} metadata")
            bundle["resources"][label] = verify_resource(archive, resource)
            archives.append(archive)
        if not official:
            digest = hashlib.sha256(
                json.dumps(bundle["resources"], sort_keys=True).encode()
            ).hexdigest()
            bundle["release"] = "custom-content-sha256:" + digest
        taxonomy.build_crosswalk_db(
            chain.from_iterable(_iter_metadata_rows(path) for path in archives),
            tmp_db,
            release=bundle["release"],
        )
        with sqlite3.connect(tmp_db) as con:
            con.execute(
                "INSERT OR REPLACE INTO meta VALUES ('source_bundle', ?)",
                (json.dumps(bundle, sort_keys=True),),
            )


def ensure_gtdb_db(
    path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    bac120_url: str = DEFAULT_BAC120_URL,
    ar53_url: str = DEFAULT_AR53_URL,
    release: str | None = None,
) -> Path:
    """Ensure a valid local crosswalk DB exists, returning its path.

    Idempotent: a valid DB present (and ``refresh`` False) returns instantly.
    Otherwise acquisition requires consent (``auto=True`` or ``BRAIDWORKS_AUTO_DOWNLOAD``);
    without it an actionable error is raised. Locking, disk precheck, and atomic publish
    are handled by ``braidworks.core.localdb.ensure_local_db``.
    """
    db_path = Path(path) if path is not None else default_db_path()

    def valid(candidate: Path) -> bool:
        if not db_is_valid(candidate):
            return False
        custom = (bac120_url, ar53_url) != (DEFAULT_BAC120_URL, DEFAULT_AR53_URL)
        if custom:
            with closing(taxonomy.open_ro(candidate)) as con:
                row = con.execute("SELECT value FROM meta WHERE key='source_bundle'").fetchone()
            if not row:
                return False
            bundle = json.loads(row[0])
            return (
                bundle.get("kind") == "custom-content"
                and bundle.get("declared_release") == release
                and all(
                    bundle["resources"][label]["url"] == url
                    for label, url in (("bac120", bac120_url), ("ar53", ar53_url))
                )
            )
        return release is None or taxonomy.db_release(candidate) == ("R" + release.lstrip("RrvV"))

    return ensure_local_db(
        db_path,
        is_valid=valid,
        build=lambda target: _build_crosswalk(
            target, bac120_url=bac120_url, ar53_url=ar53_url, release=release
        ),
        consent_message=_consent_message(db_path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=_MIN_FREE_BYTES,
    )
