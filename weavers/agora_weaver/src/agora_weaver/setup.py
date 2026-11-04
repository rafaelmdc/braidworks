"""ensure_agora_db — acquiring the local AGORA2 reaction repertoire (agora_weaver-specific).

The ``core`` group needs no download (the crosswalk is bundled). This module builds only
the optional ``reactions`` DB: it streams the AGORA2 SBML archive (~2.17 GB) for per-model
reaction membership and fetches the VMH reaction crosswalk (abbreviation -> subsystem/EC/
KEGG/Rhea) from the ``/_api/reactions/`` endpoint, writing both into a SQLite via
``dataset.build_reaction_db``. Generic mechanics (consent gate, streamed download, disk
precheck, lock, atomic publish) live in ``braidworks.core.localdb``.

This function never prompts, so it stays deterministic and easy to test.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

from braidworks.core.localdb import USER_AGENT, auto_consented, ensure_local_db
from braidworks.core.localdb import default_db_path as _core_default_db_path
from braidworks.core.localdb import download as _download
from braidworks.core.localdb import md5_file as _md5_file

from agora_weaver import dataset

logger = logging.getLogger("agora_weaver.setup")

DEFAULT_SBML_URL = (
    "https://www.vmh.life/files/reconstructions/AGORA2/version2.01/"
    "sbml_files_fixed/zipped/AGORA2_models/AGORA2_SBML.zip"
)
DEFAULT_REACTIONS_API = "https://www.vmh.life/_api/reactions/"
# VMH's current single-model service. Explicit family selection prevents the
# default/multiple-version route from silently returning AGORA1 or APOLLO.
# It generates SBML for this release; it is not the byte-identical archive XML.
DEFAULT_INDIVIDUAL_SBML_BASE = (
    "https://vmh.life/api/getMicrobeReconstructions?version=agora2_2.01&format=sbml&id="
)

_NAMESPACE = "agora"
_DB_FILENAME = "agora2_reactions.sqlite"
_SBML_CACHE_DIRNAME = "agora2_sbml_models"
# ~2.17 GB SBML archive + the built SQLite + temporary headroom.
_MIN_FREE_BYTES = 8 * 1024**3

__all__ = [
    "DEFAULT_INDIVIDUAL_SBML_BASE",
    "DEFAULT_REACTIONS_API",
    "DEFAULT_SBML_URL",
    "auto_consented",
    "db_is_valid",
    "default_db_path",
    "default_sbml_cache_dir",
    "ensure_agora_db",
    "ensure_model_sbml",
    "individual_sbml_url",
]


def default_sbml_cache_dir() -> Path:
    """Per-user cache dir for lazily-downloaded individual AGORA2 SBML models."""
    return default_db_path().parent / _SBML_CACHE_DIRNAME


class InvalidSBML(ValueError):
    """A model artifact is malformed or is not an SBML model."""


def _validate_model_id(reconstruction_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", reconstruction_id):
        raise ValueError("reconstruction_id must be a safe model identifier")


def validate_model_sbml(path: Path) -> str:
    """Stream-validate complete XML with an SBML root and one identified model.

    This is structural validation, not complete SBML schema/biochemical validation.
    """
    root_seen = False
    model_id = None
    depth = 0
    try:
        for event, element in ET.iterparse(path, events=("start", "end")):
            tag = element.tag.rsplit("}", 1)[-1]
            if event == "start":
                if not root_seen:
                    if tag != "sbml" or (
                        element.tag.startswith("{")
                        and not element.tag.startswith("{http://www.sbml.org/sbml/")
                    ):
                        raise InvalidSBML("model artifact must have an SBML root")
                    root_seen = True
                elif depth == 1 and tag == "model":
                    if model_id is not None or not element.get("id"):
                        raise InvalidSBML("SBML must contain one model with a nonempty id")
                    model_id = element.get("id")
                depth += 1
            else:
                depth -= 1
                element.clear()
    except ET.ParseError as exc:
        raise InvalidSBML(f"invalid SBML XML: {exc}") from exc
    if model_id is None:
        raise InvalidSBML("SBML artifact contains no identified model")
    return model_id


def model_sbml_is_valid(path: Path) -> bool:
    try:
        validate_model_sbml(path)
        return True
    except (OSError, InvalidSBML):
        return False


def individual_sbml_url(
    reconstruction_id: str, *, base_url: str = DEFAULT_INDIVIDUAL_SBML_BASE
) -> str:
    """VMH URL for a single AGORA2 model's SBML file."""
    _validate_model_id(reconstruction_id)
    if base_url == DEFAULT_INDIVIDUAL_SBML_BASE:
        return f"{base_url}{reconstruction_id}"
    # Explicit caller-configured directories retain the original XML convention.
    return f"{base_url.rstrip('/')}/{reconstruction_id}.xml"


def ensure_model_sbml(
    reconstruction_id: str,
    *,
    cache_dir: str | Path | None = None,
    base_url: str = DEFAULT_INDIVIDUAL_SBML_BASE,
    auto: bool = False,
) -> Path | None:
    """Ensure a single model's SBML is cached locally; return its path (or None).

    Cached files are structurally validated before return. A missing model is downloaded only if consented
    (``auto`` or ``BRAIDWORKS_AUTO_DOWNLOAD``); otherwise ``None`` (a requested unavailable model becomes a backend error record). Size varies by reconstruction; no archive download.
    """
    _validate_model_id(reconstruction_id)
    directory = Path(cache_dir) if cache_dir is not None else default_sbml_cache_dir()
    target = directory / f"{reconstruction_id}.xml"
    if model_sbml_is_valid(target):
        return target
    if not auto_consented(auto):
        return None

    def build(staged: Path) -> None:
        _download(
            individual_sbml_url(reconstruction_id, base_url=base_url),
            staged,
            label=f"AGORA2 model {reconstruction_id}",
        )
        validate_model_sbml(staged)

    return ensure_local_db(
        target,
        is_valid=model_sbml_is_valid,
        build=build,
        consent_message=f"AGORA2 SBML for {reconstruction_id} requires download consent",
        auto=auto,
        min_free_bytes=32 * 1024**2,
    )


def default_db_path() -> Path:
    """Per-user default reaction-DB path (``BRAIDWORKS_DATA_DIR`` overrides the cache dir)."""
    return _core_default_db_path(_NAMESPACE, _DB_FILENAME)


def db_is_valid(path: Path) -> bool:
    """Return whether ``path`` is a readable, populated reaction DB."""
    return dataset.reaction_db_is_valid(path)


def _consent_message(db_path: Path) -> str:
    return (
        f"AGORA2 reaction database not found at {db_path}.\n"
        "The `core` reconstruction output works without it (the crosswalk is bundled);\n"
        "only the `reactions` repertoire needs this DB, built from the AGORA2 SBML archive\n"
        "(~2.17 GB download). To create it:\n"
        "  - call: build_agora_weaver(auto_setup=True)\n"
        "  - or set: BRAIDWORKS_AUTO_DOWNLOAD=1"
    )


def _fetch_reaction_crosswalk(
    api_url: str,
) -> Iterator[tuple[str, str | None, str | None, str | None, str | None]]:
    """Stream ``(abbreviation, subsystem, ec, kegg, rhea)`` from the VMH reactions API."""
    url: str | None = f"{api_url}?page_size=1000"
    seen = 0
    while url:
        # VMH sits behind Cloudflare, which 403s the default urllib agent — send the
        # shared braidworks User-Agent (same as localdb.download).
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        for r in body.get("results") or []:
            abbrev = (r.get("abbreviation") or "").strip()
            if not abbrev:
                continue
            seen += 1
            yield (
                abbrev,
                (r.get("subsystem") or "").strip() or None,
                (r.get("ecnumber") or "").strip() or None,
                (r.get("keggId") or "").strip() or None,
                (str(r.get("rhea")).strip() if r.get("rhea") else None),
            )
        url = body.get("next")
    logger.info("fetched %d VMH reaction crosswalk rows", seen)


def _build_reaction_db(tmp_db: Path, *, sbml_url: str, reactions_api: str) -> None:
    """Build callback for ``ensure_local_db``: download SBML zip + fetch crosswalk -> SQLite."""
    archive = tmp_db.parent / "AGORA2_SBML.zip"
    logger.info("acquiring AGORA2 SBML archive -> %s (%s)", archive, sbml_url)
    try:
        _download(sbml_url, archive, label="Downloading AGORA2 SBML archive")
        content_hash = _md5_file(archive)
        written = dataset.build_reaction_db(
            archive,
            _fetch_reaction_crosswalk(reactions_api),
            tmp_db,
            content_hash=content_hash,
            annotation_source=reactions_api,
            sbml_source=sbml_url,
        )
        logger.info("AGORA2 reaction DB built: %s (%d reaction rows)", tmp_db, written)
    finally:
        archive.unlink(missing_ok=True)


def ensure_agora_db(
    path: str | Path | None = None,
    *,
    auto: bool = False,
    refresh: bool = False,
    sbml_url: str = DEFAULT_SBML_URL,
    reactions_api: str = DEFAULT_REACTIONS_API,
) -> Path:
    """Ensure a valid local reaction DB exists, returning its path.

    Idempotent: a valid DB present (and ``refresh`` False) returns instantly.
    Otherwise acquisition requires consent (``auto=True`` or ``BRAIDWORKS_AUTO_DOWNLOAD``);
    without it an actionable error is raised. Locking, disk precheck, and atomic publish
    are handled by ``braidworks.core.localdb.ensure_local_db``.
    """
    db_path = Path(path) if path is not None else default_db_path()
    return ensure_local_db(
        db_path,
        is_valid=db_is_valid,
        build=lambda target: _build_reaction_db(
            target, sbml_url=sbml_url, reactions_api=reactions_api
        ),
        consent_message=_consent_message(db_path),
        auto=auto,
        refresh=refresh,
        min_free_bytes=_MIN_FREE_BYTES,
    )
