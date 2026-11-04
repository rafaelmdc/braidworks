"""The local backend for wikipedia_weaver — a pageviews SQLite built from a dump.

Answers ``describe_pageviews`` (``wikipedia.title`` -> ``wikipedia.pageviews``) from a
local ``title -> views`` table (see ``setup.py`` for the dump->SQLite build). Unlike
the api backend this is O(1) per title with no network, so it scales to the
million-title scopes the fame ranking must cover.

One owned read-only connection per batch; the sync
SELECTs run off the event loop via ``asyncio.to_thread``. Construction is cheap and
never raises — ``is_configured()`` reports whether the DB is present and built.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from braidworks.core import BackendBase, LookupRecord
from braidworks.core.source_identity import SourceBinding

from ..measurement import InvalidScope, measurement, month_window, title_provenance
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
        self._source = SourceBinding(
            self._db_path, lambda con: dict(con.execute("SELECT key, value FROM metadata"))
        )
        self._configured = db_is_valid(self._db_path)
        self._fingerprint: str | None = None

    def is_configured(self) -> bool:
        return self._configured

    def fingerprint(self) -> str:
        if not self._configured:
            return "enwiki-pageviews-unbuilt"
        return self._source.fingerprint()

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
        records = await asyncio.to_thread(self._lookup, titles, params or {})
        if "series" in groups_to_compute:
            for record in records:
                if record.found:
                    record.values["wikipedia.pageviews.series"] = [
                        {
                            "month": record.values["wikipedia.pageviews.measurement"][
                                "start_month"
                            ],
                            "views": record.values["wikipedia.pageviews"],
                        }
                    ]
                    record.values["wikipedia.pageviews.title"] = title_provenance(
                        record.query["wikipedia.title"]
                    )
        return records

    def _lookup(self, titles: list[str], params: dict[str, Any]) -> list[LookupRecord]:
        with self._source.session() as con:
            dump_month = con.execute(
                "SELECT value FROM metadata WHERE key='dump_month'"
            ).fetchone()[0]
            parser_complete = json.loads(
                con.execute("SELECT value FROM metadata WHERE key='parser_coverage'").fetchone()[0]
            )["complete"]
            try:
                months = month_window(params.get("months", 1), params.get("end_month", dump_month))
                agent = params.get("agent", "user")
                if months != [dump_month] or agent != "user":
                    raise InvalidScope(
                        f"local supports only month={dump_month}, months=1, agent=user"
                    )
            except InvalidScope as exc:
                return [LookupRecord(query={"wikipedia.title": t}, error=str(exc)) for t in titles]
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
                    out.append(
                        LookupRecord(
                            query=query,
                            found=False,
                            error=None
                            if parser_complete
                            else "incomplete dump parsing cannot establish article absence",
                        )
                    )
                else:
                    out.append(
                        LookupRecord(
                            query=query,
                            found=True,
                            values={
                                "wikipedia.pageviews": int(row[0]),
                                "wikipedia.pageviews.measurement": measurement(
                                    months, agent, 1, complete=parser_complete
                                ),
                            },
                            warnings=(
                                (
                                    f"Pageviews: monthly dump {dump_month}, user, all-access; "
                                    f"dump parser complete={str(parser_complete).lower()}."
                                ),
                            ),
                        )
                    )
            return out
