"""The api backend for wikipedia_weaver — the Wikimedia REST pageviews API.

For each English Wikipedia article title, sums monthly pageviews over a trailing
window (default 12 months) into a single popularity count. The pageviews endpoint
is per-article (no batch form), so the batch is fired concurrently with
``asyncio.gather`` — never awaited one-at-a-time in a loop.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``).

Guide: weaverkit/docs/implementing-backends.md
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from braidworks.core import BackendBase, LookupRecord, is_not_found_status

BASE_URL = "https://wikimedia.org/api/rest_v1/"
_USER_AGENT = "Cladewright/0.1 (https://github.com/rafaelmdc; rafaelmdcorreia@gmail.com)"
_WINDOW_MONTHS = 12


def _window(now: datetime) -> tuple[str, str]:
    """(start, end) timestamps (YYYYMMDD00) for the trailing window of whole months."""
    end = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    months = (now.year * 12 + (now.month - 1)) - _WINDOW_MONTHS
    start = datetime(months // 12, months % 12 + 1, 1, tzinfo=timezone.utc)
    return start.strftime("%Y%m%d00"), end.strftime("%Y%m%d00")


class WikipediaApiBackend(BackendBase):
    """api backend — calls the keyless Wikimedia pageviews API."""

    name = "api"

    def __init__(
        self, *, base_url: str = BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._configured = True  # keyless service — always usable

    def is_configured(self) -> bool:
        return self._configured or self._client is not None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return self._client

    def fingerprint(self) -> str:
        # Pageviews accrue monthly; bucket the cache by the window-end month.
        _, end = _window(datetime.now(timezone.utc))
        return "enwiki-pageviews-" + end[:6]

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        start, end = _window(datetime.now(timezone.utc))
        titles = [str(q.get("wikipedia.title", "")).strip() for q in queries]

        async def one(title: str) -> LookupRecord:
            query = {"wikipedia.title": title}
            if not title:
                return LookupRecord(query=query, found=False)
            path = (
                "/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/"
                f"{quote(title, safe='')}/monthly/{start}/{end}"
            )
            try:
                resp = await self._http().get(path, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    return LookupRecord(query=query, found=False)  # no data for this title
                return LookupRecord(query=query, found=False,
                                    error=f"pageviews HTTP {exc.response.status_code}")
            except httpx.HTTPError as exc:
                return LookupRecord(query=query, found=False, error=f"pageviews failed: {exc}")

            total = sum(int(item.get("views", 0)) for item in resp.json().get("items", []))
            return LookupRecord(query=query, found=True, values={"wikipedia.pageviews": total})

        # Per-article endpoint: issue the batch concurrently, preserve input order.
        return list(await asyncio.gather(*(one(t) for t in titles)))
