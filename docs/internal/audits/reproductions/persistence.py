import asyncio
import os
import sqlite3
import tempfile
import time
from pathlib import Path

from braidworks.core.localdb import LOCK_STALE_SECONDS, BuildLock
from taxonomy_resolver.cache import _ensure_cache_database
from wikipedia_weaver.backends.local import WikipediaLocalBackend


def database(path, month, views):
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE pageviews(title TEXT PRIMARY KEY,views INTEGER);"
    )
    con.execute("INSERT INTO metadata VALUES (?,?)", ("dump_month", month))
    con.execute("INSERT INTO pageviews VALUES (?,?)", ("Example", views))
    con.commit()
    con.close()


async def main():
    with tempfile.TemporaryDirectory(prefix="braidworks-persistence-audit-") as tmp:
        root = Path(tmp)
        con = sqlite3.connect(":memory:")
        with con:
            con.execute("CREATE TABLE example(value)")
        assert con.execute("SELECT 1").fetchone() == (1,)
        con.close()
        print("D01: connection transaction context leaves connection open")
        target = root / "build.sqlite"
        lock = target.with_name(target.name + ".lock")
        lock.write_text(str(os.getpid()))
        old = time.time() - LOCK_STALE_SECONDS - 1
        os.utime(lock, (old, old))
        assert BuildLock(target)._reclaim_if_stale()
        assert not lock.exists()
        print("D02: stale lock with current living process PID was reclaimed")
        path = root / "pageviews.sqlite"
        replacement = root / "replacement.sqlite"
        database(path, "2026-01", 10)
        backend = WikipediaLocalBackend(path)
        before = backend.fingerprint()
        database(replacement, "2026-02", 20)
        os.replace(replacement, path)
        result = await backend.fetch(
            "describe_pageviews",
            [{"wikipedia.title": "Example"}],
            requested_outputs=frozenset({"wikipedia.pageviews"}),
            groups_to_compute=frozenset({"g"}),
        )
        assert result[0].values["wikipedia.pageviews"] == 20
        assert backend.fingerprint() == before == "enwiki-pageviews-2026-01"
        print("D03: new dump value 20 returned under cached old dump fingerprint 2026-01")
        cache = root / "review.sqlite"
        _ensure_cache_database(cache, create_indexes=False)
        replacement = root / "empty.sqlite"
        sqlite3.connect(replacement).close()
        os.replace(replacement, cache)
        _ensure_cache_database(cache, create_indexes=False)
        con = sqlite3.connect(cache)
        try:
            con.execute("SELECT * FROM reviewed_mappings")
        except sqlite3.OperationalError as exc:
            assert "no such table" in str(exc)
            print("D04: process-global initialized path skipped schema after file replacement")
        else:
            raise AssertionError("replacement schema unexpectedly initialized")
        finally:
            con.close()


asyncio.run(main())
