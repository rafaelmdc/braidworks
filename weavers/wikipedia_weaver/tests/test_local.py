"""Unit tests for the dump-backed local backend (no network, no real dump)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wikipedia_weaver.backends.local import WikipediaLocalBackend
from wikipedia_weaver.setup import _parse_lines, build_pageviews_db, db_is_valid

# A few lines of a pageview_complete monthly dump: enwiki desktop+mobile for Brown_bear
# (94587 + 84187), a French row and a Wikidata row that must be ignored, and a malformed
# row. The trailing token is the hourly-distribution code; the count is the field before.
_DUMP = [
    "en.wikipedia Brown_bear 4623963 desktop 94587 J1K2",
    "en.m.wikipedia Brown_bear 4623963 mobile-web 84187 G3H4",
    "fr.wikipedia Ours_brun 99 desktop 5000 Z9",
    "en.wikipedia Aardvark 778 desktop 12345 A1",
    "en.wikipedia broken_row_no_count",
    "en.wikipedia Tardigrade 999 desktop notanint B2",
]


def test_parse_lines_filters_and_extracts() -> None:
    rows = list(_parse_lines(_DUMP))
    assert ("Brown_bear", 94587) in rows
    assert ("Brown_bear", 84187) in rows
    assert ("Aardvark", 12345) in rows
    # Non-enwiki, malformed, and non-integer counts are dropped.
    assert all(title != "Ours_brun" for title, _ in rows)
    assert all(title != "Tardigrade" for title, _ in rows)
    assert all(title != "broken_row_no_count" for title, _ in rows)


def _fixture_db(tmp_path: Path) -> Path:
    db = tmp_path / "pv.sqlite"
    build_pageviews_db(db, source=iter(_DUMP), month="202505")
    return db


def test_build_db_sums_access_methods(tmp_path: Path) -> None:
    db = _fixture_db(tmp_path)
    assert db_is_valid(db)


@pytest.mark.asyncio
async def test_local_backend_lookup(tmp_path: Path) -> None:
    backend = WikipediaLocalBackend(_fixture_db(tmp_path))
    assert backend.is_configured()
    assert backend.fingerprint() == "enwiki-pageviews-202505"

    records = await backend.fetch(
        "describe_pageviews",
        [{"wikipedia.title": "Brown_bear"}, {"wikipedia.title": "Nonexistent"}],
        requested_outputs=frozenset({"wikipedia.pageviews"}),
        groups_to_compute=frozenset({"core"}),
    )
    # Desktop + mobile summed into one popularity figure.
    assert records[0].found and records[0].values["wikipedia.pageviews"] == 94587 + 84187
    # A title absent from the dump month → no data (caller treats missing as fame 0).
    assert not records[1].found


def test_unconfigured_backend_is_safe(tmp_path: Path) -> None:
    backend = WikipediaLocalBackend(tmp_path / "missing.sqlite")
    assert not backend.is_configured()
    assert backend.fingerprint() == "enwiki-pageviews-unbuilt"
