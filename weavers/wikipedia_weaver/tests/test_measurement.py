"""Period and agent define the metric, not just its scalar count."""

from datetime import UTC, datetime

import httpx
import pytest
from tests.test_local import _fixture_db
from wikipedia_weaver.backends.api import WikipediaApiBackend, _window
from wikipedia_weaver.backends.local import WikipediaLocalBackend


def test_window_contains_exactly_twelve_completed_months_including_year_boundary():
    assert _window(datetime(2026, 10, 9, tzinfo=UTC)) == ("2025100100", "2026090100")
    assert _window(datetime(2026, 1, 1, tzinfo=UTC)) == ("2025010100", "2025120100")


def item(month, views=10):
    return {
        "project": "en.wikipedia",
        "article": "Brown_bear",
        "access": "all-access",
        "agent": "user",
        "granularity": "monthly",
        "timestamp": month + "0100",
        "views": views,
    }


async def api_record(rows):
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"items": rows})),
    ) as client:
        return (
            await WikipediaApiBackend(client=client).fetch(
                "describe_pageviews",
                [{"wikipedia.title": "Brown_bear"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
                params={"months": 2, "end_month": "202502", "agent": "user"},
            )
        )[0]


@pytest.mark.parametrize("rows", [[item("202501"), item("202501")], [item("202503")]])
async def test_duplicate_or_unrequested_bin_is_error(rows):
    assert (await api_record(rows)).error


async def test_missing_bins_report_partial_subtotal():
    record = await api_record([item("202501", 0)])
    assert record.found and record.values["wikipedia.pageviews"] == 0
    scope = record.values["wikipedia.pageviews.measurement"]
    assert scope["observed_bins"] == 1 and scope["requested_bins"] == 2
    assert scope["complete"] is False and record.warnings


async def test_local_exposes_scope_and_rejects_different_explicit_metric(tmp_path):
    backend = WikipediaLocalBackend(_fixture_db(tmp_path))

    async def fetch(params):
        return (
            await backend.fetch(
                "describe_pageviews",
                [{"wikipedia.title": "Brown_bear"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
                params=params,
            )
        )[0]

    record = await fetch({"months": 1, "end_month": "202505", "agent": "user"})
    scope = record.values["wikipedia.pageviews.measurement"]
    assert scope["start_month"] == scope["end_month"] == "202505"
    assert scope["agent"] == "user" and scope["complete"] is None
    for params in [{"months": 12}, {"agent": "all-agents"}, {"end_month": "202504"}]:
        assert (await fetch(params)).error
