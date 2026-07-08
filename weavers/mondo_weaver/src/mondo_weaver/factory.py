"""Builders for mondo_weaver — how the weaver is assembled from its backends.

- ``build_mondo_weaver()`` — the ZERO-CONFIG introspection builder (``weaverkit verify``).
- ``build_mondo_weaver_configured(...)`` — real use: ensures the local DB (downloading the
  MONDO OBO on first use if consented), then wires the backend.
- ``build_mondo_weaver_fixture()`` — canned tiny DB, for ``verify --strict`` / tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from braidworks.core import BaseWeaver

from mondo_weaver.backends.local import MondoLocalBackend
from mondo_weaver.setup import ensure_mondo_db
from mondo_weaver.weaver import MondoWeaver


def build_mondo_weaver(**_config: Any) -> BaseWeaver:
    """Zero-config introspection builder (``weaverkit verify``'s entry point).

    Wires the local backend present-but-possibly-unconfigured (``is_configured() == False``
    until the DB is built). For real use call ``build_mondo_weaver_configured``.
    """
    return MondoWeaver({"local": MondoLocalBackend()})


def build_mondo_weaver_configured(
    *,
    db_path: str | Path | None = None,
    auto_setup: bool = False,
    refresh: bool = False,
    **_config: Any,
) -> BaseWeaver:
    """Configured builder for real use: ensures the local DB, then wires the backend.

    With ``auto_setup=True`` (or ``BRAIDWORKS_AUTO_DOWNLOAD=1``) the ~53 MB OBO is
    downloaded and parsed on first use; otherwise an explicit ``db_path`` must already
    point at a built DB, or an actionable error is raised. ``refresh=True`` re-downloads.
    """
    path = ensure_mondo_db(db_path, auto=auto_setup, refresh=refresh)
    return MondoWeaver({"local": MondoLocalBackend(path)})


def build_mondo_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` / tests — canned data, no network."""
    from mondo_weaver.fixture import fixture_db_path

    return MondoWeaver({"local": MondoLocalBackend(fixture_db_path())})
