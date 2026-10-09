"""Requested resource scope and parser provenance stay bound to the acquired dump."""

import bz2
import hashlib
import json
import sqlite3
from io import BytesIO

import pytest
from braidworks.core import BackendConfigurationError
from wikipedia_weaver.backends.local import WikipediaLocalBackend
from wikipedia_weaver.factory import build_wikipedia_weaver
from wikipedia_weaver.setup import build_pageviews_db, db_is_valid, ensure_pageviews_db

ROWS = "en.wikipedia Known 1 desktop 10 x\nen.wikipedia Zero 2 mobile-web 0 y\n"


def metadata(path):
    with sqlite3.connect(path) as con:
        return dict(con.execute("SELECT key,value FROM metadata"))


def test_compressed_dump_hash_and_valid_measurement_coverage(tmp_path):
    raw = bz2.compress(ROWS.encode())
    path = tmp_path / "source.sqlite"
    build_pageviews_db(path, source=BytesIO(raw), month="202501")
    meta = metadata(path)
    assert meta["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert json.loads(meta["measurement"])["agent"] == "user"
    assert json.loads(meta["parser_coverage"]) == {
        "total_rows": 2,
        "irrelevant_rows": 0,
        "valid_rows": 2,
        "invalid_rows": 0,
        "complete": True,
    }
    assert db_is_valid(path)


async def test_invalid_rows_and_negative_counts_are_diagnosed_not_added(tmp_path):
    path = tmp_path / "source.sqlite"
    lines = [ROWS, "en.wikipedia Known 1 desktop -5 x\n", "en.wikipedia Broken\n"]
    build_pageviews_db(path, source=iter("".join(lines).splitlines(keepends=True)), month="202501")
    coverage = json.loads(metadata(path)["parser_coverage"])
    assert coverage["invalid_rows"] == 2 and not coverage["complete"]
    backend = WikipediaLocalBackend(path)
    records = await backend.fetch(
        "describe_pageviews",
        [{"wikipedia.title": title} for title in ["Known", "Zero", "Broken"]],
        requested_outputs=frozenset(),
        groups_to_compute=frozenset(),
    )
    assert records[0].values["wikipedia.pageviews"] == 10
    assert records[1].found and records[1].values["wikipedia.pageviews"] == 0
    assert records[2].error and not records[2].found
    assert not records[0].values["wikipedia.pageviews.measurement"]["complete"]


def test_month_mismatch_never_silently_reuses_or_overwrites_existing_db(tmp_path):
    path = tmp_path / "source.sqlite"
    build_pageviews_db(path, source=ROWS.splitlines(), month="202501")
    original = path.read_bytes()
    with pytest.raises(BackendConfigurationError, match="month=202501, requested=202502"):
        ensure_pageviews_db(path, year=2025, month=2, auto=True)
    assert path.read_bytes() == original


def test_prebuilt_path_infers_actual_month_and_partial_date_is_rejected(tmp_path):
    path = tmp_path / "source.sqlite"
    build_pageviews_db(path, source=ROWS.splitlines(), month="202501")
    assert set(build_wikipedia_weaver(db_path=path)._backends) == {"local"}
    with pytest.raises(BackendConfigurationError, match="both"):
        build_wikipedia_weaver(db_path=path, year=2025)


def test_year_month_alone_select_local_and_explicit_dump_month_must_agree(tmp_path, monkeypatch):
    from wikipedia_weaver import factory

    path = tmp_path / "source.sqlite"
    build_pageviews_db(path, source=ROWS.splitlines(), month="202501")
    calls = []
    monkeypatch.setattr(
        factory, "ensure_pageviews_db", lambda *args, **kwargs: calls.append(kwargs) or path
    )
    assert set(build_wikipedia_weaver(year=2025, month=1)._backends) == {"local"}
    assert calls[0]["year"] == 2025 and calls[0]["month"] == 1
    with pytest.raises(BackendConfigurationError, match="filename month"):
        ensure_pageviews_db(
            tmp_path / "absent",
            year=2025,
            month=2,
            dump_path=tmp_path / "pageviews-202501-user.bz2",
            auto=True,
        )


@pytest.mark.parametrize("stamp", ["202500", "202513", "garbage", "000001"])
def test_invalid_dump_month_rejected(tmp_path, stamp):
    with pytest.raises(ValueError):
        build_pageviews_db(tmp_path / "source.sqlite", source=ROWS.splitlines(), month=stamp)
