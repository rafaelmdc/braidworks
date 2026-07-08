"""Builders for gmrepo_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_gmrepo_weaver()`` — the ZERO-CONFIG *introspection* builder that
  ``weaverkit verify`` calls. It wires the declared backend present (possibly
  unconfigured), so the manifest is complete and fingerprint/golden checks can run.
- ``build_gmrepo_weaver_configured(...)`` — the real-use builder: ensures the local
  DB (fetching from GMrepo on first use if consented), then wires the backend.
- ``build_gmrepo_weaver_fixture()`` — canned tiny DB, for ``verify --strict`` / tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from braidworks.core import BaseWeaver

from gmrepo_weaver.backends.local import GmrepoLocalBackend
from gmrepo_weaver.setup import ensure_gmrepo_db
from gmrepo_weaver.weaver import GmrepoWeaver


def build_gmrepo_weaver(**_config: Any) -> BaseWeaver:
    """Zero-config introspection builder (``weaverkit verify``'s entry point).

    Wires the local backend present-but-possibly-unconfigured (it reports
    ``is_configured() == False`` until the DB is built). For real use call
    ``build_gmrepo_weaver_configured``.
    """
    return GmrepoWeaver({"local": GmrepoLocalBackend()})


def build_gmrepo_weaver_configured(
    *,
    db_path: str | Path | None = None,
    auto_setup: bool = False,
    refresh: bool = False,
    profile_phenotypes: list[str] | None = None,
    profile_max_runs: int = 200,
    **_config: Any,
) -> BaseWeaver:
    """Configured builder for real use: ensures the local DB, then wires the backend.

    With ``auto_setup=True`` (or ``BRAIDWORKS_AUTO_DOWNLOAD=1``) the few-MB DB is built
    from the GMrepo API on first use; otherwise an explicit ``db_path`` must already
    point at a built DB, or an actionable error is raised. ``refresh=True`` rebuilds.

    Pass ``profile_phenotypes`` (MeSH ids) to also crawl up to ``profile_max_runs`` per-run
    sample profiles for each — the ``gmrepo.sample_profiles`` substrate for the co-occurrence
    layer. Since the build is idempotent, adding profiles to an existing DB needs ``refresh=True``.
    """
    path = ensure_gmrepo_db(
        db_path,
        auto=auto_setup,
        refresh=refresh,
        profile_phenotypes=profile_phenotypes,
        profile_max_runs=profile_max_runs,
    )
    return GmrepoWeaver({"local": GmrepoLocalBackend(path)})


def build_gmrepo_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` / tests — canned data, no network."""
    from gmrepo_weaver.fixture import fixture_db_path

    return GmrepoWeaver({"local": GmrepoLocalBackend(fixture_db_path())})
