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
from braidworks.core.http_pacing import PacedHTTPClient

logger = logging.getLogger("pdbe_weaver.api")

DEFAULT_BASE_URL = "https://www.ebi.ac.uk/pdbe/api"
DEFAULT_LIMIT = 25  # top structures to surface in ids/records (count stays the true total)
_BEST_CHUNK = 100  # accessions per bulk best-structure request
_SUMMARY_CHUNK = 200  # pdb ids per POST /pdb/entry/summary request (keeps the body bounded)
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
    return (
        -(rec.get("coverage") or 0.0),
        rec.get("resolution") or _WORST_RESOLUTION,
        rec.get("pdb_id") or "",
    )


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

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return PacedHTTPClient(self._client, "pdbe")

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        # describe_structure drills PDB ids; list_structures lists a protein's structures.
        if capability_id == "describe_structure":
            return await self._describe_structures(queries)
        return await self._list_structures(queries)

    async def _list_structures(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        accessions = [str(q.get("protein.uniprot.accession", "")).strip() for q in queries]
        distinct = sorted({accession for accession in accessions if accession})
        mappings: dict[str, list[dict[str, Any]]] = {}
        errors: dict[str, str] = {}
        for start in range(0, len(distinct), _BEST_CHUNK):
            chunk = distinct[start : start + _BEST_CHUNK]
            try:
                if len(chunk) == 1:
                    response = await self._http().get(f"/mappings/best_structures/{chunk[0]}")
                else:
                    response = await self._http().post(
                        "/mappings/best_structures",
                        content=",".join(chunk),
                        headers={"Content-Type": "text/plain"},
                    )
                response.raise_for_status()
                mappings.update({key.upper(): rows for key, rows in response.json().items()})
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    errors.update(dict.fromkeys(chunk, f"PDBe API error: {format_exc(exc)}"))
            except httpx.HTTPError as exc:
                errors.update(dict.fromkeys(chunk, f"PDBe API error: {format_exc(exc)}"))
        records = []
        for query, accession in zip(queries, accessions):
            rows = mappings.get(accession.upper()) or []
            if accession in errors:
                records.append(LookupRecord(query=query, error=errors[accession]))
            elif rows:
                records.append(
                    LookupRecord(query=query, found=True, values=_extract(rows, self._limit))
                )
            else:
                records.append(LookupRecord(query=query, found=False))
        return records

    async def _describe_structures(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        """PDB ids -> their summaries via the bulk ``POST /pdb/entry/summary`` endpoint.

        The whole batch is sent as a comma-separated id list (chunked to keep the body
        bounded) instead of one ``GET /pdb/entry/summary/{id}`` per structure. PDBe keys
        the response by pdb id, so results are matched back case-insensitively.
        """
        pids = [str(q.get("pdb.id", "")).strip() for q in queries]
        distinct = sorted({p for p in pids if p})
        summaries: dict[str, dict[str, Any]] = {}
        try:
            for start in range(0, len(distinct), _SUMMARY_CHUNK):
                chunk = distinct[start : start + _SUMMARY_CHUNK]
                if not chunk:
                    continue
                resp = await self._http().post(
                    "/pdb/entry/summary",
                    content=",".join(chunk),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
                for key, rows in (resp.json() or {}).items():
                    if rows:
                        summaries[key.lower()] = rows[0]
        except httpx.HTTPStatusError as exc:
            if not is_not_found_status(exc.response.status_code):
                logger.warning("PDBe detail failed: %s", exc)
                err = f"PDBe API error: {format_exc(exc)}"
                return [LookupRecord(query=q, error=err) for q in queries]
        except httpx.HTTPError as exc:
            logger.warning("PDBe detail failed: %s", exc)
            err = f"PDBe API error: {format_exc(exc)}"
            return [LookupRecord(query=q, error=err) for q in queries]

        records: list[LookupRecord] = []
        for query, pid in zip(queries, pids):
            obj = summaries.get(pid.lower()) if pid else None
            if obj is None:
                records.append(LookupRecord(query=query, found=False))
            else:
                records.append(LookupRecord(query=query, found=True, values=_describe(pid, obj)))
        return records
