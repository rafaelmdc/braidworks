"""The api backend for pdbe_weaver — the keyless EBI PDBe REST API.

Strategy: a UniProt ``protein.uniprot.accession`` is sent to
``GET /pdbe/api/mappings/best_structures/{accession}``. PDBe returns one row per
(structure, chain) mapping, so a protein yields many rows. The backend:
  * **dedups to distinct PDB structures** (``pdb_id``), keeping the best-covering chain;
  * orders them best-first — coverage descending, then resolution ascending, then pdb_id;
  * emits ``structure.pdb.ids`` (top ``limit``), ``structure.pdb.count`` (total distinct),
    and ``structure.pdb.records`` (top ``limit`` with method/resolution/coverage).

**Determinism:** the fixed sort means the same accession always yields the same list.
An accession with no structures (PDBe 404, or an empty mapping) is a clean ``NO_MATCH``.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (best_structures for P04637).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status

logger = logging.getLogger("pdbe_weaver.api")

DEFAULT_BASE_URL = "https://www.ebi.ac.uk/pdbe/api"
DEFAULT_LIMIT = 25  # top structures to surface in ids/records (count stays the true total)
_WORST_RESOLUTION = 1e9  # sort sentinel for entries with no resolution (NMR/EM sometimes)


def _record(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "pdb_id": raw.get("pdb_id"),
        "method": raw.get("experimental_method"),
        "resolution": raw.get("resolution"),
        "coverage": raw.get("coverage"),
    }


def _rank(rec: dict[str, Any]) -> tuple[float, float]:
    """Higher is better: most coverage, then best (lowest) resolution."""
    return (rec.get("coverage") or 0.0, -(rec.get("resolution") or _WORST_RESOLUTION))


def _sort_key(rec: dict[str, Any]) -> tuple[float, float, str]:
    """Best-first total order: coverage desc, resolution asc, then pdb_id (stable)."""
    return (-(rec.get("coverage") or 0.0), rec.get("resolution") or _WORST_RESOLUTION,
            rec.get("pdb_id") or "")


def _extract(rows: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    """Dedup PDBe (structure, chain) rows to distinct best structures, ordered."""
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        rec = _record(raw)
        pid = rec["pdb_id"]
        if not pid:
            continue
        if pid not in by_id or _rank(rec) > _rank(by_id[pid]):
            by_id[pid] = rec
    ordered = sorted(by_id.values(), key=_sort_key)
    top = ordered[:limit]
    return {
        # The fan dimension (set_outputs): every distinct PDB id, so a caller can fan out
        # one child per structure. Uncapped — structure.pdb.ids/records are the top-N
        # display; the executor's max_expansion bounds any runaway.
        "pdb.id": [r["pdb_id"] for r in ordered],
        "structure.pdb.ids": [r["pdb_id"] for r in top],
        "structure.pdb.count": len(by_id),  # true total distinct; ids/records are the top N
        "structure.pdb.records": top,
    }


def _describe(pdb_id: str, obj: dict[str, Any]) -> dict[str, Any]:
    """One PDBe entry summary (/pdb/entry/summary/{id}) -> describe_structure outputs."""
    method = obj.get("experimental_method") or []
    return {
        "structure.pdb.title": obj.get("title"),
        "structure.pdb.method": method[0] if method else None,
        "structure.pdb.release_date": obj.get("release_date"),
        "structure.pdb.detail": {
            "pdb_id": pdb_id,
            "title": obj.get("title"),
            "method": method,
            "release_date": obj.get("release_date"),
            "deposition_date": obj.get("deposition_date"),
            "authors": obj.get("entry_authors"),
        },
    }


class PdbeApiBackend(BackendBase):
    """PDBe REST backend. Always configured — the API is free, no key."""

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
        """PDBe REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the REST API contract."""
        return "pdbe-api-v1"

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return self._client

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        # describe_structure drills one PDB id; list_structures lists a protein's structures.
        if capability_id == "describe_structure":
            return [await self._describe_one(q) for q in queries]
        records: list[LookupRecord] = []
        for query in queries:
            accession = str(query.get("protein.uniprot.accession", "")).strip()
            records.append(await self._resolve_one(query, accession))
        return records

    async def _describe_one(self, query: dict[str, Any]) -> LookupRecord:
        """One pdb.id -> that structure's detail via /pdb/entry/summary/{id}."""
        pid = str(query.get("pdb.id", "")).strip()
        if not pid:
            return LookupRecord(query=query, found=False)
        try:
            resp = await self._http().get(f"/pdb/entry/summary/{pid}")
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPStatusError as exc:
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("PDBe detail failed for %r: %s", pid, exc)
            return LookupRecord(query=query, error=f"PDBe API error: {format_exc(exc)}")
        except httpx.HTTPError as exc:
            logger.warning("PDBe detail failed for %r: %s", pid, exc)
            return LookupRecord(query=query, error=f"PDBe API error: {format_exc(exc)}")
        # Response is {pdb_id: [summary]}; casing can differ, so fall back to the sole value.
        rows = body.get(pid) or (next(iter(body.values()), []) if body else [])
        if not rows:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_describe(pid, rows[0]))

    async def _resolve_one(self, query: dict[str, Any], accession: str) -> LookupRecord:
        if not accession:
            return LookupRecord(query=query, found=False)
        try:
            resp = await self._http().get(f"/mappings/best_structures/{accession}")
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPStatusError as exc:
            # PDBe 404s (or 400s a malformed) accession with no structure mapping —
            # a NO_MATCH, not an error (shared 400/404 rule, braidworks.core.http).
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("PDBe lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"PDBe API error: {format_exc(exc)}")
        except httpx.HTTPError as exc:  # network/timeout problem is a per-entity error
            logger.warning("PDBe lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"PDBe API error: {format_exc(exc)}")

        # Response is {accession: [rows]}; the key casing can differ, so fall back to the
        # sole value if the exact key is absent.
        rows = body.get(accession) or (next(iter(body.values()), []) if body else [])
        if not rows:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_extract(rows, self._limit))
