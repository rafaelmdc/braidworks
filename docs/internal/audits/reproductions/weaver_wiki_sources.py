import asyncio
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from wikidata_weaver.backends.api import WikidataApiBackend, _sparql_literal
from wikipedia_weaver.backends.api import WikipediaApiBackend, _window
from wikipedia_weaver.setup import build_pageviews_db, ensure_pageviews_db


async def main():
    for body in [{}, [], {"results": {"bindings": [None]}}]:
        async with httpx.AsyncClient(
            base_url="https://fixture",
            transport=httpx.MockTransport(lambda r, body=body: httpx.Response(200, json=body)),
        ) as c:
            try:
                result = await WikidataApiBackend(client=c).fetch(
                    "resolve_taxon",
                    [{"organism.scientific_name": "Ursus arctos"}],
                    requested_outputs=frozenset(),
                    groups_to_compute=frozenset(),
                )
                print("Wikidata shape", body, "status", result[0].status)
            except Exception as e:  # noqa: BLE001 - reports escaped exception types
                print("Wikidata shape escapes", type(e).__name__)
    calls = []

    def handler(r):
        calls.append(r.url.path)
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as c:
        result = await WikipediaApiBackend(client=c).fetch(
            "describe_pageviews",
            [{"wikipedia.title": "Brown_bear"}, {"wikipedia.title": "Brown_bear"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
        print(
            "Wikipedia malformed object",
            result[0].found,
            result[0].values,
            "duplicate requests",
            len(calls),
        )
    print("Wikipedia window", _window(datetime(2026, 10, 8, tzinfo=UTC)))
    print("Unescaped newline SPARQL", repr(_sparql_literal("one\ntwo")))
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "views.sqlite"
        build_pageviews_db(db, source=["en.wikipedia Brown_bear 1 desktop 12 A1\n"], month="202501")
        selected = ensure_pageviews_db(db, year=2025, month=2, auto=False)
        with sqlite3.connect(selected) as con:
            print(
                "Requested February returned",
                con.execute("SELECT value FROM metadata WHERE key='dump_month'").fetchone()[0],
            )


asyncio.run(main())
