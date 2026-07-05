"""The api backend for gtdb_weaver — the live GTDB search API (keyless).

Resolves a GTDB *species name* via ``GET /search/gtdb?search=<name>`` on
``gtdb-api.ecogenomic.org`` — the online fallback when the local crosswalk isn't
built. It is name-based only: a query carrying just an NCBI taxid (no name) is a
miss here (the local backend is authoritative for taxids). The HTTP client is
**injectable** (``client=``) so tests drive it offline with an ``httpx.MockTransport``
(see ``fixture.py`` / ``build_gtdb_weaver_fixture``).

Guide: weaverkit/docs/implementing-backends.md
Worked example: weavers/ncbi_weaver/src/ncbi_weaver/backends/datasets_v2.py
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from braidworks.core import BackendBase
from braidworks.core import LookupRecord
from braidworks.core import format_exc, is_not_found_status

from gtdb_weaver import taxonomy

# Base URL of the GTDB API (the api.gtdb.ecogenomic.org host has a broken cert).
BASE_URL = "https://gtdb-api.ecogenomic.org"


class GtdbApiBackend(BackendBase):
    """api backend — the keyless GTDB name-search API."""

    name = "api"

    def __init__(
        self, *, base_url: str = BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client
        # A keyless API is usable as-is; an injected client (the fixture) also counts.
        self._configured = True

    def is_configured(self) -> bool:
        return self._configured or self._client is not None

    def _http(self) -> httpx.AsyncClient:
        """The HTTP client, lazily created if none was injected."""
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return self._client

    def fingerprint(self) -> str:
        return "gtdb_weaver-api-v1"

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        # One record per query, in order — the API search is per-name, so fire the
        # distinct names concurrently and map results back positionally.
        names = [_query_name(q) for q in queries]
        distinct = sorted({n for n in names if n})
        fetched = await asyncio.gather(
            *(self._search(name) for name in distinct), return_exceptions=True
        )
        by_name: dict[str, LookupRecord | Exception] = dict(zip(distinct, fetched))

        records: list[LookupRecord] = []
        for query, name in zip(queries, names):
            if not name:
                # Taxid-only queries can't be resolved by the name-search API.
                records.append(LookupRecord(query=query, found=False))
                continue
            result = by_name.get(name)
            if isinstance(result, Exception):
                records.append(
                    LookupRecord(query=query, error=f"GTDB API error: {format_exc(result)}")
                )
                continue
            records.append(_relabel(result, query))
        return records

    async def _search(self, name: str) -> LookupRecord:
        """Resolve one GTDB species name to a record (found/miss); raises only on HTTP errors."""
        try:
            resp = await self._http().get(
                "/search/gtdb",
                params={"search": name, "page": 1, "itemsPerPage": 100, "searchField": "all"},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query={"organism.scientific_name": name}, found=False)
            raise
        rows = resp.json().get("rows") or []
        row = _best_row(rows, name)
        if row is None:
            return LookupRecord(query={"organism.scientific_name": name}, found=False)
        gtdb_taxonomy = row.get("gtdbTaxonomy") or ""
        taxon_id, lineage = taxonomy.parse_gtdb_taxonomy(gtdb_taxonomy)
        if taxon_id is None:
            return LookupRecord(query={"organism.scientific_name": name}, found=False)
        return LookupRecord(
            query={"organism.scientific_name": name},
            found=True,
            values={"gtdb.taxon.id": taxon_id, "gtdb.lineage": lineage},
        )


def _query_name(query: dict[str, Any]) -> str | None:
    """The GTDB species name to search for, if this query carries one."""
    name = query.get("organism.scientific_name")
    if name in (None, ""):
        return None
    return str(name).strip()


def _best_row(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Pick the row best matching ``name``: exact species match wins, then a rep, then first."""
    if not rows:
        return None
    target = name.strip().lower()

    def species_of(row: dict[str, Any]) -> str | None:
        tid, _ = taxonomy.parse_gtdb_taxonomy(row.get("gtdbTaxonomy") or "")
        if tid and tid.startswith("s__"):
            return tid[3:].strip().lower()
        return None

    exact = [r for r in rows if species_of(r) == target]
    pool = exact or rows
    for r in pool:
        if r.get("isGtdbSpeciesRep"):
            return r
    return pool[0]


def _relabel(record: LookupRecord, query: dict[str, Any]) -> LookupRecord:
    """Re-key a per-name record onto the caller's original query dict."""
    if record.found:
        return LookupRecord(query=query, found=True, values=dict(record.values))
    if record.error:
        return LookupRecord(query=query, error=record.error)
    return LookupRecord(query=query, found=False)
