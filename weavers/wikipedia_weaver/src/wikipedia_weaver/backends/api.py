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
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
from braidworks.core import BackendBase, LookupRecord, is_not_found_status
from braidworks.core.http_pacing import PacedHTTPClient

BASE_URL = "https://wikimedia.org/api/rest_v1/"
_USER_AGENT = "Cladewright/0.1 (https://github.com/rafaelmdc; rafaelmdcorreia@gmail.com)"
_WINDOW_MONTHS = 12


class _InvalidResponse(ValueError):
    """Expected source schema or correlation failure, rather than a coding fault."""


def _window(now: datetime) -> tuple[str, str]:
    """(start, end) timestamps (YYYYMMDD00) for the trailing window of whole months."""
    end = datetime(now.year, now.month, 1, tzinfo=UTC)
    months = (now.year * 12 + (now.month - 1)) - _WINDOW_MONTHS
    start = datetime(months // 12, months % 12 + 1, 1, tzinfo=UTC)
    return start.strftime("%Y%m%d00"), end.strftime("%Y%m%d00")


def _pageviews(body: Any) -> int | None:
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise _InvalidResponse("pageviews response must contain an items list")
    if not body["items"]:
        return None
    total = 0
    for item in body["items"]:
        if not isinstance(item, dict):
            raise _InvalidResponse("pageviews item must be an object")
        views = item.get("views")
        if isinstance(views, bool) or not isinstance(views, int) or views < 0:
            raise _InvalidResponse("pageviews views must be a non-negative integer")
        total += views
    return total


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

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return PacedHTTPClient(self._client, "wikipedia")

    def fingerprint(self) -> str:
        # Pageviews accrue monthly; bucket the cache by the window-end month.
        _, end = _window(datetime.now(UTC))
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
        start, end = _window(datetime.now(UTC))
        titles = [str(q.get("wikipedia.title") or "").strip() for q in queries]

        async def one(query: dict[str, Any], title: str) -> LookupRecord:
            if not title:
                return LookupRecord(query=query, found=False)
            path = (
                "/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/"
                f"{quote(title, safe='')}/monthly/{start}/{end}"
            )
            try:
                resp = await self._http().get(path, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
                total = _pageviews(resp.json())
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    return LookupRecord(query=query, found=False)  # no data for this title
                return LookupRecord(
                    query=query, found=False, error=f"pageviews HTTP {exc.response.status_code}"
                )
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                return LookupRecord(query=query, found=False, error=f"pageviews failed: {exc}")

            if total is None:
                return LookupRecord(query=query, found=False)
            return LookupRecord(query=query, found=True, values={"wikipedia.pageviews": total})

        # Per-article endpoint: issue the batch concurrently, preserve input order.
        return list(await asyncio.gather(*(one(q, t) for q, t in zip(queries, titles))))
