"""Builders for agora_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_agora_weaver()`` — the ZERO-CONFIG *introspection* builder that
  ``weaverkit verify`` calls. The single ``local`` backend is always configured (its
  ``core`` crosswalk is bundled); the reaction DB may be absent, in which case only the
  ``reactions`` group is unavailable. Never raises for missing data.
- ``build_agora_weaver_configured()`` — ensures the reaction DB (consent-gated download).
- ``build_agora_weaver_fixture()`` — wires the tiny offline reaction DB for goldens.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from braidworks.core import BaseWeaver

from agora_weaver.backends.local import AgoraLocalBackend
from agora_weaver.setup import auto_consented, db_is_valid, default_db_path, ensure_agora_db
from agora_weaver.weaver import AgoraWeaver


def build_agora_weaver(
    *,
    db_path: str | Path | None = None,
    auto_setup: bool = False,
    refresh: bool = False,
    **_config: Any,
) -> BaseWeaver:
    """Build an AgoraWeaver with the local backend.

    ``core`` (reconstruction id + genome) always works — the crosswalk is bundled. The
    ``reactions`` repertoire needs the reaction DB: it's ensured (consent-gated download)
    when ``db_path`` is given or ``auto_setup`` is set; otherwise the backend points at
    the default DB path present-or-not (this zero-config form is what ``weaverkit verify``
    and entry-point discovery call as ``build_agora_weaver()``).
    """
    reaction_db: str | Path | None = db_path
    if db_path is not None or auto_setup:
        reaction_db = _ensure_reaction_db(db_path, auto_setup=auto_setup, refresh=refresh)
    return AgoraWeaver({"local": AgoraLocalBackend(reaction_db)})


def _interactive() -> bool:
    """Whether we may prompt the user (both stdin and stdout are a TTY)."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _prompt_for_setup(target: Path) -> bool:
    """Announce the one-time reaction-DB build and confirm; default is No."""
    print(
        "The AGORA2 `reactions` repertoire needs a reaction database that is not present yet.\n"
        "  source: AGORA2 SBML archive (~2.17 GB download)\n"
        "  builds: a reaction-membership SQLite (the `core` output already works without it)\n"
        f"  target: {target}",
        file=sys.stderr,
    )
    return input("Build it now? [y/N] ").strip().lower() in {"y", "yes"}


def _ensure_reaction_db(db_path: str | Path | None, *, auto_setup: bool, refresh: bool) -> Path:
    """Resolve (and if needed acquire) the reaction DB path per the consent rules."""
    target = Path(db_path) if db_path is not None else default_db_path()
    if db_is_valid(target) and not refresh:
        return target
    consented = auto_consented(auto_setup)
    if not consented and _interactive():
        consented = _prompt_for_setup(target)
    return ensure_agora_db(target, auto=consented, refresh=refresh)


def build_agora_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` — bundled crosswalk + tiny reaction DB, no network."""
    from agora_weaver.fixture import fixture_reaction_db_path

    return AgoraWeaver({"local": AgoraLocalBackend(fixture_reaction_db_path())})


def build_agora_weaver_configured(**config: Any) -> BaseWeaver:
    """Configured builder — ensures the reaction DB (raises without consent if it must download)."""
    return build_agora_weaver(auto_setup=True, **config)
