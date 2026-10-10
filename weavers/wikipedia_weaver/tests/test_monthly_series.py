"""Observed bins retain missing-month semantics and require no extra requests."""

import httpx
from wikipedia_weaver.backends.api import WikipediaApiBackend


async def test_series_preserves_observed_bins_and_detaches_duplicate_results():
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "project": "en.wikipedia",
                        "article": "Brown_bear",
                        "granularity": "monthly",
                        "timestamp": stamp,
                        "access": "all-access",
                        "agent": "all-agents",
                        "views": views,
                    }
                    for stamp, views in [("2025030100", 12), ("2025010100", 8)]
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(response)
    ) as client:
        backend = WikipediaApiBackend(client=client)
        queries = [{"wikipedia.title": "Brown bear"}, {"wikipedia.title": "Brown bear"}]
        records = await backend.fetch(
            "describe_pageviews",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"series"}),
            params={"months": 3, "end_month": "202503"},
        )
        assert len(calls) == 1
        values = records[0].values
        assert values["wikipedia.pageviews.series"] == [
            {"month": "202501", "views": 8},
            {"month": "202503", "views": 12},
        ]
        assert values["wikipedia.pageviews"] == 20
        assert values["wikipedia.pageviews.measurement"]["complete"] is False
        assert values["wikipedia.pageviews.title"]["requested_title"] == "Brown bear"
        assert values["wikipedia.pageviews.title"]["article_key"] == "Brown_bear"
        values["wikipedia.pageviews.series"][0]["views"] = 999
        assert records[1].values["wikipedia.pageviews.series"][0]["views"] == 8
        default = await backend.fetch(
            "describe_pageviews",
            queries[:1],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"core"}),
            params={"months": 3, "end_month": "202503"},
        )
        assert "wikipedia.pageviews.series" not in default[0].values


async def test_dump_series_exposes_one_month_and_parser_coverage(tmp_path):
    from tests.test_local import _fixture_db
    from wikipedia_weaver.backends.local import WikipediaLocalBackend

    records = await WikipediaLocalBackend(_fixture_db(tmp_path)).fetch(
        "describe_pageviews",
        [{"wikipedia.title": "Brown_bear"}],
        requested_outputs=frozenset(),
        groups_to_compute=frozenset({"series"}),
    )
    values = records[0].values
    assert values["wikipedia.pageviews.series"] == [{"month": "202505", "views": 178774}]
    assert values["wikipedia.pageviews.measurement"]["complete"] is False
    assert values["wikipedia.pageviews.title"]["project"] == "en.wikipedia"
