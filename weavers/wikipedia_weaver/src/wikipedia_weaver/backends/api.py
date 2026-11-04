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

import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx
from braidworks.core import BackendBase, LookupRecord, is_not_found_status
from braidworks.core.concurrency import map_bounded
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

from wikipedia_weaver.measurement import InvalidScope, measurement, month_window, title_provenance

BASE_URL = "https://wikimedia.org/api/rest_v1/"
_USER_AGENT = "Braidworks (https://github.com/rafaelmdc/braidworks)"
_WINDOW_MONTHS = 12


class _InvalidResponse(ValueError):
    """Expected source schema or correlation failure, rather than a coding fault."""


def _window(now: datetime) -> tuple[str, str]:
    """(start, end) timestamps (YYYYMMDD00) for the trailing window of whole months."""
    months = month_window(_WINDOW_MONTHS, now=now)
    return months[0] + "0100", months[-1] + "0100"


def _pageviews(body: Any, *, months: list[str], title: str, agent: str) -> tuple[int | None, int]:
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise _InvalidResponse("pageviews response must contain an items list")
    if not body["items"]:
        return None, 0
    total = 0
    seen: set[str] = set()
    for item in body["items"]:
        if not isinstance(item, dict):
            raise _InvalidResponse("pageviews item must be an object")
        views = item.get("views")
        if isinstance(views, bool) or not isinstance(views, int) or views < 0:
            raise _InvalidResponse("pageviews views must be a non-negative integer")
        timestamp = item.get("timestamp")
        if not isinstance(timestamp, str) or timestamp not in {month + "0100" for month in months}:
            raise _InvalidResponse("pageviews timestamp is outside the requested monthly bins")
        if timestamp in seen:
            raise _InvalidResponse("duplicate monthly pageviews bin")
        seen.add(timestamp)
        expected = {
            "project": "en.wikipedia",
            "access": "all-access",
            "agent": agent,
            "granularity": "monthly",
        }
        if any(item.get(key) != value for key, value in expected.items()):
            raise _InvalidResponse("pageviews response measurement differs from request")
        if str(item.get("article", "")).replace(" ", "_") != title.replace(" ", "_"):
            raise _InvalidResponse("pageviews response article differs from request")
        total += views
    return total, len(seen)


class WikipediaApiBackend(HTTPClientLifecycle, BackendBase):
    """api backend — calls the keyless Wikimedia pageviews API."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        client: httpx.AsyncClient | None = None,
        months: int = 12,
        end_month: str | None = None,
        agent: str = "all-agents",
        max_concurrency: int = 4,
    ) -> None:
        self._configure_client(client, base_url)
        if (
            isinstance(max_concurrency, bool)
            or not isinstance(max_concurrency, int)
            or max_concurrency < 1
        ):
            raise ValueError("max_concurrency must be a positive integer")
        self._max_concurrency = max_concurrency
        month_window(months, end_month)
        if agent not in {"all-agents", "user", "spider", "automated"}:
            raise ValueError("unsupported pageviews agent")
        self._months, self._end_month, self._agent = months, end_month, agent
        self._configured = True  # keyless service — always usable

    def is_configured(self) -> bool:
        return self._configured or self._client is not None

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return PacedHTTPClient(self._client, "wikipedia", default_rate=5.0)

    def fingerprint(self) -> str:
        # Pageviews accrue monthly; bucket the cache by the window-end month.
        months = month_window(self._months, self._end_month)
        return remote_fingerprint(
            "wikipedia_weaver-api",
            self._base_url,
            contract=f"enwiki-pageviews-{months[0]}-{months[-1]}-{self._agent}",
        )

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        options = params or {}
        try:
            months = month_window(
                options.get("months", self._months), options.get("end_month", self._end_month)
            )
            agent = options.get("agent", self._agent)
            if agent not in {"all-agents", "user", "spider", "automated"}:
                raise InvalidScope("unsupported pageviews agent")
        except InvalidScope as exc:
            return [LookupRecord(query=q, error=f"pageviews scope: {exc}") for q in queries]
        start, end = months[0] + "0100", months[-1] + "0100"
        titles = [str(q.get("wikipedia.title") or "").strip() for q in queries]

        async def one(query: dict[str, Any], title: str) -> LookupRecord:
            if not title:
                return LookupRecord(query=query, found=False)
            path = (
                f"/metrics/pageviews/per-article/en.wikipedia/all-access/{agent}/"
                f"{quote(title, safe='')}/monthly/{start}/{end}"
            )
            try:
                resp = await self._http().get(path, headers={"User-Agent": _USER_AGENT})
                resp.raise_for_status()
                body = resp.json()
                total, observed = _pageviews(body, months=months, title=title, agent=agent)
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
                return LookupRecord(
                    query=query,
                    error=f"No monthly bins acquired for {months[0]}..{months[-1]}; "
                    "measurement completeness is not established.",
                )
            values = {
                "wikipedia.pageviews": total,
                "wikipedia.pageviews.measurement": measurement(
                    months, agent, observed, complete=observed == len(months)
                ),
            }
            if "series" in groups_to_compute:
                values["wikipedia.pageviews.series"] = [
                    {"month": item["timestamp"][:6], "views": item["views"]}
                    for item in sorted(body["items"], key=lambda item: item["timestamp"])
                ]
                values["wikipedia.pageviews.title"] = title_provenance(title)
            return LookupRecord(
                query=query,
                found=True,
                values=values,
                warnings=(
                    (
                        f"Pageviews: {months[0]}..{months[-1]}, {agent}, all-access; "
                        f"observed {observed}/{len(months)} monthly bins."
                    ),
                ),
            )

        # Per-article endpoint: issue the batch concurrently, preserve input order.
        distinct = sorted(set(titles))

        async def resolve(title: str) -> LookupRecord:
            return await one({"wikipedia.title": title}, title)

        fetched = await map_bounded(distinct, resolve, limit=self._max_concurrency)
        by_title = dict(zip(distinct, fetched))
        return [
            replace(by_title[title], query=query, values=deepcopy(by_title[title].values))
            for query, title in zip(queries, titles)
        ]
