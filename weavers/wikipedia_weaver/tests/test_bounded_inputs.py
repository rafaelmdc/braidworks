"""Distinct titles use bounded workers and duplicate projections are detached."""

import asyncio
from urllib.parse import unquote

import httpx
from wikipedia_weaver.backends.api import WikipediaApiBackend


async def test_distinct_titles_are_bounded_and_duplicates_are_detached():
    active = peak = 0
    called = []

    async def handler(request):
        nonlocal active, peak
        title = unquote(request.url.path.split("/monthly/")[0].rsplit("/", 1)[-1])
        active += 1
        peak = max(peak, active)
        called.append(title)
        try:
            await asyncio.sleep(0.002)
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "project": "en.wikipedia",
                            "article": title,
                            "granularity": "monthly",
                            "timestamp": "2025010100",
                            "access": "all-access",
                            "agent": "all-agents",
                            "views": 12,
                        }
                    ]
                },
            )
        finally:
            active -= 1

    async with httpx.AsyncClient(
        base_url="https://source.example", transport=httpx.MockTransport(handler)
    ) as client:
        backend = WikipediaApiBackend(
            client=client, months=1, end_month="202501", max_concurrency=2
        )
        queries = [{"wikipedia.title": title} for title in ["one", "two", "one", "three", "four"]]
        records = await backend.fetch(
            "describe_pageviews",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
        assert peak <= 2 and len(called) == 4 and all(record.found for record in records)
        assert [record.query for record in records] == queries
        records[0].values["wikipedia.pageviews.measurement"]["agent"] = "changed"
        assert records[2].values["wikipedia.pageviews.measurement"]["agent"] == "all-agents"
        await backend.aclose()
        assert not client.is_closed
