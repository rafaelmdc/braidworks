"""The local backend for wikipedia_weaver — a pageviews SQLite built from a dump.

Answers ``describe_pageviews`` (``wikipedia.title`` -> ``wikipedia.pageviews``) from a
local ``title -> views`` table (see ``setup.py`` for the dump->SQLite build). Unlike
the api backend this is O(1) per title with no network, so it scales to the
million-title scopes the fame ranking must cover.

One read-only connection per thread (``threading.local``), created lazily; the sync
SELECTs run off the event loop via ``asyncio.to_thread``. Construction is cheap and
never raises — ``is_configured()`` reports whether the DB is present and built.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path
from typing import Any

from braidworks.core import BackendBase, LookupRecord

from ..setup import db_is_valid


class WikipediaLocalBackend(BackendBase):
    """local backend — Wikipedia pageviews from a SQLite built off a monthly dump."""

    name = "local"

    def __init__(self, db_path: str | Path) -> None:
        # Backbone contract: construct cheap, never raise for a missing DB. The hard
        # "you asked for local but it's absent" error lives in the configured builder
        # (factory -> ensure_pageviews_db), so a zero-config introspection build can
        # wire an unconfigured backend (manifest-complete, golden skips) with no download.
        self._db_path = Path(db_path)
        self._tl = threading.local()
        self._configured = db_is_valid(self._db_path)
        self._fingerprint: str | None = None

    def is_configured(self) -> bool:
        return self._configured

    def _con(self) -> sqlite3.Connection:
        con = getattr(self._tl, "con", None)
        if con is None:
            con = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
            self._tl.con = con
        return con

    def fingerprint(self) -> str:
        """The dump month backing this DB — the cache key. Stable even when unbuilt."""
        if self._fingerprint is None:
            if not self._configured:
                return "enwiki-pageviews-unbuilt"
            row = self._con().execute(
                "SELECT value FROM metadata WHERE key='dump_month'"
            ).fetchone()
            self._fingerprint = "enwiki-pageviews-" + (row[0] if row else "unversioned")
        return self._fingerprint

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        titles = [str(q.get("wikipedia.title", "")).strip() for q in queries]
        return await asyncio.to_thread(self._lookup, titles)

    def _lookup(self, titles: list[str]) -> list[LookupRecord]:
        con = self._con()
        out: list[LookupRecord] = []
        for title in titles:
            query = {"wikipedia.title": title}
            if not title:
                out.append(LookupRecord(query=query, found=False))
                continue
            row = con.execute(
                "SELECT views FROM pageviews WHERE title = ?", (title,)
            ).fetchone()
            if row is None:
                # No row for this article in the dump month → no pageview data.
                out.append(LookupRecord(query=query, found=False))
            else:
                out.append(
                    LookupRecord(query=query, found=True,
                                 values={"wikipedia.pageviews": int(row[0])})
                )
        return out
