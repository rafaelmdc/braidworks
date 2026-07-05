"""Builders for gtdb_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_gtdb_weaver()`` — the ZERO-CONFIG *introspection* builder that
  ``weaverkit verify`` calls. It wires every declared backend present (possibly
  unconfigured), so the manifest is complete and fingerprint/golden checks can run.
  It never raises for missing data.
- a CONFIGURED builder (you write it, usually domain-named) — takes real config
  (db paths, API keys, injected clients) and may raise if nothing is usable. See
  ``ncbi_weaver``'s ``build_ncbi_weaver`` for a worked example; a commented
  skeleton is at the bottom of this file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx

from braidworks.core import BaseWeaver, BackendConfigurationError

from gtdb_weaver.backends.local import GtdbLocalBackend
from gtdb_weaver.backends.api import BASE_URL as _API_BASE_URL, GtdbApiBackend
from gtdb_weaver.setup import auto_consented, db_is_valid, default_db_path, ensure_gtdb_db
from gtdb_weaver.weaver import GtdbWeaver


def build_gtdb_weaver(
    *,
    db_path: str | Path | None = None,
    auto_setup: bool = False,
    refresh: bool = False,
    enable_api: bool = False,
    api_base_url: str | None = None,
    api_client: httpx.AsyncClient | None = None,
    **_config: Any,
) -> BaseWeaver:
    """Build a GtdbWeaver, wiring the local and/or api backends from config.

    The local backend is configured when ``db_path`` is given or ``auto_setup`` is set;
    its crosswalk DB is ensured (consent-gated, see ``setup.ensure_gtdb_db``). The api
    backend is configured when ``enable_api`` is set or a client is injected. With **no**
    backend-selecting argument, returns the zero-config **introspection** weaver — both
    backends declared, the keyless api usable and local present-but-unconfigured (its
    default DB path, not built) — which is what ``weaverkit verify`` and entry-point
    discovery call as ``build_gtdb_weaver()``.
    """
    backends: dict[str, Any] = {}
    if db_path is not None or auto_setup:
        resolved = _ensure_local_db(db_path, auto_setup=auto_setup, refresh=refresh)
        backends["local"] = GtdbLocalBackend(resolved)
    if enable_api or api_client is not None:
        backends["api"] = GtdbApiBackend(base_url=api_base_url or _API_BASE_URL, client=api_client)
    if not backends:
        # Zero-config introspection form: every declared backend present-but-possibly-
        # unconfigured (local at its default path without building; the api needs no data).
        backends["local"] = GtdbLocalBackend()
        backends["api"] = GtdbApiBackend()
    return GtdbWeaver(backends)


def _interactive() -> bool:
    """Whether we may prompt the user (both stdin and stdout are a TTY)."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _prompt_for_setup(target: Path) -> bool:
    """Announce the one-time crosswalk build and confirm; default is No."""
    print(
        "The local GTDB backend needs a crosswalk database that is not present yet.\n"
        "  source: GTDB bac120 + ar53 metadata (~150 MB download)\n"
        "  builds: a small SQLite crosswalk\n"
        f"  target: {target}",
        file=sys.stderr,
    )
    return input("Build it now? [y/N] ").strip().lower() in {"y", "yes"}


def _ensure_local_db(db_path: str | Path | None, *, auto_setup: bool, refresh: bool) -> Path:
    """Resolve (and if needed acquire) the crosswalk DB path per the consent rules."""
    target = Path(db_path) if db_path is not None else default_db_path()
    if db_is_valid(target) and not refresh:
        return target
    consented = auto_consented(auto_setup)
    if not consented and _interactive():
        consented = _prompt_for_setup(target)
    return ensure_gtdb_db(target, auto=consented, refresh=refresh)


def build_gtdb_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` — no network.

    Wires the *local* backend against the bundled fixture crosswalk (the goldens'
    ``golden_backend``) and the *api* backend against a canned ``httpx.MockTransport``,
    so both backends' contract/golden tests run offline and reproducibly.
    """
    from gtdb_weaver.fixture import fixture_db_path, mock_client

    return GtdbWeaver(
        {
            "local": GtdbLocalBackend(fixture_db_path()),
            "api": GtdbApiBackend(client=mock_client()),
        }
    )


def build_gtdb_weaver_configured(**config: Any) -> BaseWeaver:
    """Configured builder — wires backends from real config; raises if none is usable."""
    weaver = build_gtdb_weaver(**config)
    if not weaver._backends:
        raise BackendConfigurationError(
            "configure at least one backend (db_path/auto_setup/enable_api)"
        )
    return weaver
