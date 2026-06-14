"""The api backend for reactome_weaver — the keyless Reactome ContentService API.

Strategy: a UniProt ``protein.uniprot.accession`` is sent to
``GET /data/mapping/UniProt/{accession}/pathways``. Reactome resolves the accession to
its protein + species itself and returns the pathways it participates in. The backend
dedups to **distinct pathways** (by Reactome stable id), orders them by stable id, and
emits ``pathway.reactome.names`` (top ``limit``), ``pathway.reactome.count`` (true total),
and ``pathway.reactome.records`` (``{st_id, name, in_disease}``).

**Determinism:** the fixed sort means the same accession always yields the same list.
An accession with no pathways (Reactome 404/400, or an empty list) is a clean ``NO_MATCH``.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (mapping/UniProt/P04637/pathways).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from braidworks.core import BackendBase, LookupRecord, is_not_found_status

logger = logging.getLogger("reactome_weaver.api")

DEFAULT_BASE_URL = "https://reactome.org/ContentService"
DEFAULT_LIMIT = 30  # top pathways to surface in names/records (count stays the true total)


def _extract(rows: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    """Dedup pathway rows to distinct pathways (by stId) and order by stId."""
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        st_id = raw.get("stId")
        if not st_id or st_id in by_id:
            continue
        by_id[st_id] = {
            "st_id": st_id,
            "name": raw.get("displayName"),
            "in_disease": raw.get("isInDisease"),
        }
    records = sorted(by_id.values(), key=lambda p: p["st_id"])
    top = records[:limit]
    return {
        "pathway.reactome.names": [r["name"] for r in top if r["name"]],
        "pathway.reactome.count": len(by_id),  # true total distinct; names/records are top N
        "pathway.reactome.records": top,
    }


class ReactomeApiBackend(BackendBase):
    """Reactome ContentService backend. Always configured — the API is free, no key."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._limit = limit

    def is_configured(self) -> bool:
        """Reactome ContentService needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the ContentService API contract."""
        return "reactome-contentservice-v1"

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
            resp = await self._http().get(f"/data/mapping/UniProt/{accession}/pathways")
            resp.raise_for_status()
            rows = resp.json()
        except httpx.HTTPStatusError as exc:
            # Reactome 404/400s an accession it can't map to pathways — a NO_MATCH, not error.
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("Reactome lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"Reactome API error: {exc}")
        except httpx.HTTPError as exc:  # network/timeout problem is a per-entity error
            logger.warning("Reactome lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"Reactome API error: {exc}")

        if not isinstance(rows, list) or not rows:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_extract(rows, self._limit))
