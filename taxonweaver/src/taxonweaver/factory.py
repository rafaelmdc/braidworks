"""build_ncbi_weaver — configuration-driven assembly of NCBITaxonWeaver.

Configures the ``local`` and ``api`` backends independently. A backend that is
not configured is simply not registered (it never poisons the weaver); the braider
can still plan against the remaining backend, and an unconfigured backend only
surfaces as ``BackendUnavailable`` if a step actually selects it with no fallback.

The local backend needs a SQLite taxonomy DB. Acquisition is gated by consent
(see ``setup.ensure_taxonomy_db``): on an interactive terminal the factory prompts;
otherwise it honors ``auto_setup`` / ``BRAIDWORKS_AUTO_DOWNLOAD`` or raises an
actionable error. The heavy ~1-minute build happens here, at construction, never
lazily inside ``resolve()``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

from braidworks.core import BackendConfigurationError

from .backends.datasets_v2 import DEFAULT_BASE_URL, DatasetsV2Backend
from .backends.local import LocalTaxonomyBackend
from .setup import (
    auto_consented,
    db_is_valid,
    default_db_path,
    ensure_taxonomy_db,
)
from .weaver import NCBITaxonWeaver


def _interactive() -> bool:
    """Return whether we may prompt the user (both stdin and stdout are a TTY)."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _prompt_for_setup(target: Path) -> bool:
    """Announce the one-time setup and ask the user to confirm; default is No."""
    print(
        "The local taxonomy backend needs a SQLite database that is not present yet.\n"
        "  source: NCBI taxdump.tar.gz (~70 MB download)\n"
        "  builds: ~1.2 GB SQLite, ~1 minute\n"
        f"  target: {target}",
        file=sys.stderr,
    )
    reply = input("Build it now? [y/N] ").strip().lower()
    return reply in {"y", "yes"}


def _ensure_local_db(
    db_path: str | Path | None,
    *,
    auto_setup: bool,
    refresh: bool,
) -> Path:
    """Resolve (and if needed acquire) the local taxonomy DB path per the consent rules."""
    target = Path(db_path) if db_path is not None else default_db_path()
    if db_is_valid(target) and not refresh:
        return target
    consented = auto_consented(auto_setup)
    if not consented and _interactive():
        consented = _prompt_for_setup(target)
    # If still not consented, ensure_taxonomy_db raises the actionable error.
    return ensure_taxonomy_db(target, auto=consented, refresh=refresh)


def build_ncbi_weaver(
    *,
    db_path: str | Path | None = None,
    cache_db_path: str | Path | None = None,
    auto_setup: bool = False,
    refresh: bool = False,
    enable_api: bool = False,
    api_base_url: str = DEFAULT_BASE_URL,
    api_key: str | None = None,
    api_client: httpx.AsyncClient | None = None,
    allow_fuzzy: bool = True,
) -> NCBITaxonWeaver:
    """Build an NCBITaxonWeaver, wiring the local and/or API backends from config.

    The local backend is configured when ``db_path`` is given or ``auto_setup`` is
    set; its DB is ensured (default path under the user cache when ``db_path`` is
    omitted). The API backend is configured when ``enable_api`` is set or a client
    is injected. At least one backend must be configured.
    """
    backends = {}
    want_local = db_path is not None or auto_setup
    if want_local:
        resolved_db = _ensure_local_db(db_path, auto_setup=auto_setup, refresh=refresh)
        backends["local"] = LocalTaxonomyBackend(resolved_db, cache_db_path=cache_db_path)
    if enable_api or api_client is not None:
        backends["api"] = DatasetsV2Backend(
            base_url=api_base_url,
            api_key=api_key,
            client=api_client,
            allow_fuzzy=allow_fuzzy,
        )
    if not backends:
        raise BackendConfigurationError(
            "build_ncbi_weaver: configure at least one backend "
            "(pass db_path or auto_setup=True for local and/or enable_api for the API backend)"
        )
    return NCBITaxonWeaver(backends)
