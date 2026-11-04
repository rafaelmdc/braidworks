"""Live end-to-end test for wikipedia_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest
from braidworks.core import Strand, StrandSet, WeaveStatus
from wikipedia_weaver import build_wikipedia_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def test_live_known_example():
    weaver = build_wikipedia_weaver()
    # "Brown_bear" is a long-standing article with substantial monthly traffic.
    ss = StrandSet.from_strands("e1", [Strand("wikipedia.title", "Brown_bear")])
    result = (
        await weaver.execute_batch(
            "describe_pageviews",
            [ss],
            requested_outputs=frozenset({"wikipedia.pageviews"}),
            backend="api",
        )
    )[0]
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced["wikipedia.pageviews"] > 10000  # a year of views, comfortably


async def test_live_monthly_series_matches_subtotal():
    async with build_wikipedia_weaver() as weaver:
        result = (
            await weaver.execute_batch(
                "describe_pageviews",
                [StrandSet.from_strands("series", [Strand("wikipedia.title", "Brown_bear")])],
                requested_outputs=frozenset(
                    {
                        "wikipedia.pageviews",
                        "wikipedia.pageviews.series",
                        "wikipedia.pageviews.title",
                    }
                ),
                params={"months": 2, "end_month": "202502"},
                backend="api",
            )
        )[0]
        assert result.status is WeaveStatus.OK
        values = {strand.type_id: strand.value for strand in result.strands}
        bins = values["wikipedia.pageviews.series"]
        assert [item["month"] for item in bins] == ["202501", "202502"]
        assert sum(item["views"] for item in bins) == values["wikipedia.pageviews"]
        assert values["wikipedia.pageviews.title"]["article_key"] == "Brown_bear"
