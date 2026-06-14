"""Builders for disbiome_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_disbiome_weaver()`` — the ZERO-CONFIG *introspection* builder that
  ``weaverkit verify`` calls. It wires every declared backend present (possibly
  unconfigured), so the manifest is complete and fingerprint/golden checks can run.
  It never raises for missing data.
- a CONFIGURED builder (you write it, usually domain-named) — takes real config
  (db paths, API keys, injected clients) and may raise if nothing is usable. See
  ``ncbi_weaver``'s ``build_ncbi_weaver`` for a worked example; a commented
  skeleton is at the bottom of this file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from braidworks.core import BaseWeaver

from disbiome_weaver.backends.local import DisbiomeLocalBackend
from disbiome_weaver.setup import ensure_disbiome_db
from disbiome_weaver.weaver import DisbiomeWeaver


def build_disbiome_weaver(**_config: Any) -> BaseWeaver:
    """Zero-config introspection builder (``weaverkit verify``'s entry point).

    Wires the local backend present-but-possibly-unconfigured (it reports
    ``is_configured() == False`` until the DB is built). For real use call
    ``build_disbiome_weaver_configured``.
    """
    return DisbiomeWeaver({"local": DisbiomeLocalBackend()})


def build_disbiome_weaver_configured(
    *,
    db_path: str | Path | None = None,
    auto_setup: bool = False,
    refresh: bool = False,
    **_config: Any,
) -> BaseWeaver:
    """Configured builder for real use: ensures the local DB, then wires the backend.

    With ``auto_setup=True`` (or ``BRAIDWORKS_AUTO_DOWNLOAD=1``) the ~7 MB DB is
    built from the Disbiome API on first use; otherwise an explicit ``db_path`` must
    already point at a built DB, or an actionable error is raised. ``refresh=True``
    rebuilds from the current API.
    """
    path = ensure_disbiome_db(db_path, auto=auto_setup, refresh=refresh)
    return DisbiomeWeaver({"local": DisbiomeLocalBackend(path)})


def build_disbiome_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` / tests — canned data, no network."""
    from disbiome_weaver.fixture import fixture_db_path

    return DisbiomeWeaver({"local": DisbiomeLocalBackend(fixture_db_path())})
