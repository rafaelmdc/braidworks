"""Builders for wikipedia_weaver — how the weaver is assembled from its backends.

Two-builder convention (see weaverkit/docs/decisions.md C/D):

- ``build_wikipedia_weaver()`` — the ZERO-CONFIG *introspection* builder that
  ``weaverkit verify`` and entry-point discovery call. With no backend-selecting
  argument it wires every declared backend present-but-possibly-unconfigured (local at
  the default DB path without downloading; the keyless api), so the manifest is complete.
- a CONFIGURED call — pass ``dump_path=`` / ``year=,month=`` (local, dump-built) and/or
  ``enable_api=True`` (live REST). The dump backend is the one that scales to the
  million-title scopes the fame ranking needs; the api stays the small-scope/dev path.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx

from braidworks.core import BackendConfigurationError, BaseWeaver

from wikipedia_weaver.backends.api import WikipediaApiBackend
from wikipedia_weaver.backends.local import WikipediaLocalBackend
from wikipedia_weaver.setup import default_db_path, ensure_pageviews_db
from wikipedia_weaver.weaver import WikipediaWeaver

_DUMP_MONTH_RE = re.compile(r"pageviews-(\d{4})(\d{2})-")


def _month_from_dump(dump_path: str | Path) -> tuple[int, int]:
    """Parse (year, month) from a ``pageviews-YYYYMM-user.bz2`` filename."""
    m = _DUMP_MONTH_RE.search(Path(dump_path).name)
    if not m:
        raise BackendConfigurationError(
            f"cannot infer year/month from dump filename {Path(dump_path).name!r}; "
            "pass year= and month= explicitly"
        )
    return int(m.group(1)), int(m.group(2))


def build_wikipedia_weaver(
    *,
    db_path: str | Path | None = None,
    dump_path: str | Path | None = None,
    year: int | None = None,
    month: int | None = None,
    auto_setup: bool = False,
    refresh: bool = False,
    enable_api: bool = False,
    api_client: httpx.AsyncClient | None = None,
    **_ignore: Any,
) -> BaseWeaver:
    """Assemble the weaver from config.

    The local backend is configured when ``db_path``/``dump_path``/``auto_setup`` is
    given: its DB is ensured (built from ``dump_path`` if provided, else downloaded for
    ``year``/``month``). The api backend is configured when ``enable_api`` or a client is
    passed. With **no** backend-selecting argument, returns the zero-config introspection
    weaver (both backends declared; local unconfigured, api keyless).
    """
    backends: dict[str, Any] = {}

    want_local = db_path is not None or dump_path is not None or auto_setup
    if want_local:
        y, mo = year, month
        if (y is None or mo is None) and dump_path is not None:
            y, mo = _month_from_dump(dump_path)
        if y is None or mo is None:
            raise BackendConfigurationError(
                "the local pageviews backend needs the dump month: pass year= and month= "
                "(or a dump_path= named pageviews-YYYYMM-user.bz2)"
            )
        resolved = ensure_pageviews_db(
            db_path, year=y, month=mo, dump_path=dump_path,
            auto=auto_setup, refresh=refresh,
        )
        backends["local"] = WikipediaLocalBackend(resolved)

    if enable_api or api_client is not None:
        backends["api"] = WikipediaApiBackend(client=api_client)

    if not backends:
        # Zero-config introspection: wire both present-but-possibly-unconfigured (local
        # points at the default DB path without downloading; api needs no local data).
        backends["local"] = WikipediaLocalBackend(default_db_path())
        backends["api"] = WikipediaApiBackend()

    return WikipediaWeaver(backends)


def build_wikipedia_weaver_fixture() -> BaseWeaver:
    """Fixture-backed weaver for ``verify --strict`` golden — canned api, no network."""
    from wikipedia_weaver.fixture import mock_client

    return WikipediaWeaver({"api": WikipediaApiBackend(client=mock_client())})


def build_wikipedia_weaver_local_fixture(db_path: str | Path) -> BaseWeaver:
    """A local-backend weaver over a prebuilt fixture pageviews DB (tests)."""
    return WikipediaWeaver({"local": WikipediaLocalBackend(db_path)})
