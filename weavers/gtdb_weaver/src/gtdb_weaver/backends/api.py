"""The api backend for gtdb_weaver — the live GTDB search API (keyless).

Resolves a GTDB *species name* via ``GET /search/gtdb?search=<name>`` on
``gtdb-api.ecogenomic.org`` — the online fallback when the local crosswalk isn't
built. It is name-based only: a query carrying just an NCBI taxid (no name) is a
miss here (the local backend serves observed genome classifications for taxids). The HTTP client is
**injectable** (``client=``) so tests drive it offline with an ``httpx.MockTransport``
(see ``fixture.py`` / ``build_gtdb_weaver_fixture``).

Guide: weaverkit/docs/implementing-backends.md
Worked example: weavers/ncbi_weaver/src/ncbi_weaver/backends/datasets_v2.py
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status
from braidworks.core.concurrency import map_bounded
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

from gtdb_weaver import taxonomy

# Base URL of the GTDB API (the api.gtdb.ecogenomic.org host has a broken cert).
BASE_URL = "https://gtdb-api.ecogenomic.org"


class GtdbApiBackend(HTTPClientLifecycle, BackendBase):
    """api backend — the keyless GTDB name-search API."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        client: httpx.AsyncClient | None = None,
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
        # A keyless API is usable as-is; an injected client (the fixture) also counts.
        self._configured = True

    def is_configured(self) -> bool:
        return self._configured or self._client is not None

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        """The HTTP client, lazily created if none was injected."""
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return PacedHTTPClient(self._client, "gtdb", default_rate=5.0)

    def fingerprint(self) -> str:
        return remote_fingerprint("gtdb_weaver-api", self._base_url, contract="gtdb_weaver-api-v1")

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

        async def search(name: str) -> LookupRecord:
            try:
                return (
                    await self._search(name, representative=True)
                    if "representative" in groups_to_compute
                    else await self._search(name)
                )
            except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                return LookupRecord(
                    query={"organism.scientific_name": name},
                    error=f"GTDB API error: {format_exc(exc)}",
                )

        fetched = await map_bounded(distinct, search, limit=self._max_concurrency)
        by_name = dict(zip(distinct, fetched))

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

    async def _search(self, name: str, *, representative: bool = False) -> LookupRecord:
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
        try:
            row = _best_row(rows, name)
        except taxonomy.AmbiguousClassification as exc:
            return LookupRecord(query={"organism.scientific_name": name}, error=str(exc))
        if row is None:
            return LookupRecord(query={"organism.scientific_name": name}, found=False)
        gtdb_taxonomy = row.get("gtdbTaxonomy") or ""
        taxon_id, lineage = taxonomy.parse_gtdb_taxonomy(gtdb_taxonomy)
        if taxon_id is None:
            return LookupRecord(query={"organism.scientific_name": name}, found=False)
        values = {"gtdb.taxon.id": taxon_id, "gtdb.lineage": lineage}
        if representative:
            accession = (
                (row.get("accession") or row.get("gid"))
                if row.get("isGtdbSpeciesRep") is True
                else None
            )
            values["gtdb.genome.representative"] = {
                "gtdb_taxon_id": taxon_id,
                "source_accession": accession,
                "release": None,
                "relation": "representative of the resolved GTDB species, not necessarily the input strain",
                "source": "observed search response; release not supplied",
                "available": accession is not None,
            }
        return LookupRecord(query={"organism.scientific_name": name}, found=True, values=values)


def _query_name(query: dict[str, Any]) -> str | None:
    """The GTDB species name to search for, if this query carries one."""
    name = query.get("organism.scientific_name")
    if name in (None, ""):
        return None
    return str(name).strip()


def _best_row(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Accept exact species matches only; reject competing classifications."""
    if not rows:
        return None
    target = name.strip().lower()

    def species_of(row: dict[str, Any]) -> str | None:
        tid, _ = taxonomy.parse_gtdb_taxonomy(row.get("gtdbTaxonomy") or "")
        if tid and tid.startswith("s__"):
            return tid[3:].strip().lower()
        return None

    exact = [r for r in rows if species_of(r) == target]
    if not exact:
        return None
    taxonomies = sorted({r.get("gtdbTaxonomy") or "" for r in exact})
    if len(taxonomies) > 1:
        raise taxonomy.AmbiguousClassification(
            "Conflicting GTDB API classifications require review: " + json.dumps(taxonomies)
        )
    return min(
        exact,
        key=lambda row: (
            not bool(row.get("isGtdbSpeciesRep")),
            str(row.get("accession") or row.get("gid") or ""),
            json.dumps(row, sort_keys=True),
        ),
    )


def _relabel(record: LookupRecord, query: dict[str, Any]) -> LookupRecord:
    """Re-key a per-name record onto the caller's original query dict."""
    if record.found:
        return LookupRecord(query=query, found=True, values=deepcopy(record.values))
    if record.error:
        return LookupRecord(query=query, error=record.error)
    return LookupRecord(query=query, found=False)
