"""The api backend for quickgo_weaver — the keyless EBI QuickGO REST API.

Strategy: a UniProt ``protein.uniprot.accession`` is sent to
``GET /annotation/search?geneProductId=...``. QuickGO returns one row *per annotation
evidence*, so a single protein yields hundreds of rows across many pages. The backend:
  * paginates (``page``/``limit``) up to a page cap, requesting ``includeFields=goName``;
  * **dedups to distinct GO terms** ``(goId -> name, aspect)``;
  * groups them by GO aspect into ``go.molecular_function`` / ``biological_process`` /
    ``cellular_component`` (term-name lists), plus ``go.count`` and ``go.records``.

**Determinism:** distinct terms are sorted by GO id, so the same accession always yields
the same lists. Completeness is bounded by ``max_pages`` (a protein with more annotation
pages than the cap is truncated — logged, not silent).

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (annotation/search for P04637).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from braidworks.core import BackendBase, LookupRecord

logger = logging.getLogger("quickgo_weaver.api")

DEFAULT_BASE_URL = "https://www.ebi.ac.uk/QuickGO/services"
_PAGE_SIZE = 200  # QuickGO's max results per page
_MAX_PAGES = 10  # cap fan-out: 10 pages * 200 = 2000 annotations (covers nearly all proteins)
# GO aspect (QuickGO value) -> produced type_id for that aspect's term-name list.
_ASPECTS = {
    "molecular_function": "go.molecular_function",
    "biological_process": "go.biological_process",
    "cellular_component": "go.cellular_component",
}


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Dedup annotation rows to distinct GO terms and group by aspect (deterministically)."""
    terms: dict[str, dict[str, Any]] = {}
    for row in rows:
        go_id = row.get("goId")
        if not go_id or go_id in terms:
            continue
        terms[go_id] = {
            "go_id": go_id,
            "name": row.get("goName"),
            "aspect": row.get("goAspect"),
        }
    records = sorted(terms.values(), key=lambda t: t["go_id"])  # stable order by GO id
    values: dict[str, Any] = {"go.count": len(records), "go.records": records}
    for aspect, type_id in _ASPECTS.items():
        names = [t["name"] for t in records if t["aspect"] == aspect and t["name"]]
        if names:
            values[type_id] = names
    return values


class QuickgoApiBackend(BackendBase):
    """QuickGO REST backend. Always configured — the API is free, no key."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        max_pages: int = _MAX_PAGES,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._max_pages = max_pages

    def is_configured(self) -> bool:
        """QuickGO REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the REST API contract."""
        return "quickgo-api-v1"

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url, timeout=30.0, headers={"Accept": "application/json"}
            )
        return self._client

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
    ) -> list[LookupRecord]:
        records: list[LookupRecord] = []
        for query in queries:
            accession = str(query.get("protein.uniprot.accession", "")).strip()
            records.append(await self._resolve_one(query, accession))
        return records

    async def _resolve_one(self, query: dict[str, Any], accession: str) -> LookupRecord:
        if not accession:
            return LookupRecord(query=query, found=False)
        try:
            rows = await self._all_annotations(accession)
        except httpx.HTTPError as exc:  # network/HTTP problem is a per-entity error
            logger.warning("QuickGO lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"QuickGO API error: {exc}")

        if not rows:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_aggregate(rows))

    async def _all_annotations(self, accession: str) -> list[dict[str, Any]]:
        """Page through annotation/search up to the page cap, collecting every row."""
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= self._max_pages:
            resp = await self._http().get(
                "/annotation/search",
                params={
                    "geneProductId": accession,
                    "limit": str(_PAGE_SIZE),
                    "page": str(page),
                    "includeFields": "goName",
                },
            )
            resp.raise_for_status()
            body = resp.json()
            rows.extend(body.get("results", []))
            total = (body.get("pageInfo") or {}).get("total", page)
            if page >= total:
                break
            page += 1
        else:
            logger.info("QuickGO annotations for %s truncated at %d pages", accession, self._max_pages)
        return rows
