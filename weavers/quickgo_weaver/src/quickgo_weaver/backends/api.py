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
pages than the cap is truncated — reported in coverage metadata and warnings).

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (annotation/search for P04637).
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status
from braidworks.core.http_pacing import PacedHTTPClient

logger = logging.getLogger("quickgo_weaver.api")

DEFAULT_BASE_URL = "https://www.ebi.ac.uk/QuickGO/services"
_ACCESSION_CHUNK = 10  # bounded multi-accession annotation query
_TERM_CHUNK = 100  # GO ids per multi-id /ontology/go/terms request (keeps the URL bounded)
_PAGE_SIZE = 200  # QuickGO's max results per page
_MAX_PAGES = 10  # cap fan-out: 10 pages * 200 = 2000 annotations (covers nearly all proteins)
# GO aspect (QuickGO value) -> produced type_id for that aspect's term-name list.
_ASPECTS = {
    "molecular_function": "go.molecular_function",
    "biological_process": "go.biological_process",
    "cellular_component": "go.cellular_component",
}


def _describe(term: dict[str, Any]) -> dict[str, Any]:
    """One GO term object (/ontology/go/terms/{id}) -> describe_go_term outputs."""
    definition = (term.get("definition") or {}).get("text")
    return {
        "go.term.name": term.get("name"),
        "go.term.aspect": term.get("aspect"),
        "go.term.definition": definition,
        "go.term.detail": {
            "id": term.get("id"),
            "name": term.get("name"),
            "aspect": term.get("aspect"),
            "definition": definition,
            "is_obsolete": term.get("isObsolete"),
        },
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
    values: dict[str, Any] = {
        # The fan dimension (set_outputs): every distinct GO id, so a caller can fan out
        # one child per term. The per-aspect lists below are descriptive term *names*.
        "go.term": [t["go_id"] for t in records],
        "go.count": len(records),
        "go.records": records,
    }
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
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        self._max_pages = max_pages

    def is_configured(self) -> bool:
        """QuickGO REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the REST API contract."""
        return "quickgo-api-v1"

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url, timeout=30.0, headers={"Accept": "application/json"}
            )
        return PacedHTTPClient(self._client, "quickgo")

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        # describe_go_term drills GO ids; list_go_terms lists a protein's terms.
        if capability_id == "describe_go_term":
            return await self._describe_terms(queries)
        return await self._list_annotations(queries)

    async def _list_annotations(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        ids = [str(q.get("protein.uniprot.accession", "")).strip().upper() for q in queries]
        distinct = sorted({accession for accession in ids if accession})
        by_id: dict[str, LookupRecord] = {}
        for start in range(0, len(distinct), _ACCESSION_CHUNK):
            chunk = distinct[start : start + _ACCESSION_CHUNK]
            if len(chunk) == 1:
                query = {"protein.uniprot.accession": chunk[0]}
                by_id[chunk[0]] = await self._resolve_one(query, chunk[0])
            else:
                by_id.update(await self._resolve_batch(chunk))
        return [
            replace(by_id[accession], query=query)
            if accession
            else LookupRecord(query=query, found=False)
            for query, accession in zip(queries, ids)
        ]

    async def _resolve_batch(self, accessions: list[str]) -> dict[str, LookupRecord]:
        queries = {accession: {"protein.uniprot.accession": accession} for accession in accessions}
        try:
            rows, source_coverage = await self._all_annotations(
                ",".join(accessions),
                max_pages=self._max_pages * len(accessions),
            )
        except httpx.HTTPStatusError as exc:
            if is_not_found_status(exc.response.status_code):
                return {a: LookupRecord(query=q, found=False) for a, q in queries.items()}
            return {
                a: LookupRecord(query=q, error=f"QuickGO API error: {format_exc(exc)}")
                for a, q in queries.items()
            }
        except httpx.HTTPError as exc:
            return {
                a: LookupRecord(query=q, error=f"QuickGO API error: {format_exc(exc)}")
                for a, q in queries.items()
            }
        grouped: dict[str, list[dict[str, Any]]] = {a: [] for a in accessions}
        for row in rows:
            echoed = str(row.get("geneProductId") or "").rsplit(":", 1)[-1].upper()
            if echoed not in grouped:
                message = "QuickGO bulk response cannot be correlated: missing or unexpected geneProductId"
                return {a: LookupRecord(query=q, error=message) for a, q in queries.items()}
            grouped[echoed].append(row)
        records = {}
        for accession, annotation_rows in grouped.items():
            cap = self._max_pages * _PAGE_SIZE
            selected = annotation_rows[:cap]
            coverage = dict(source_coverage)
            coverage["query_scope"] = accessions
            coverage["source_total_annotations"] = source_coverage["total_annotations"]
            coverage["total_annotations"] = (
                len(annotation_rows) if source_coverage["complete"] is True else None
            )
            coverage["observed_annotations"] = len(selected)
            if len(annotation_rows) > cap:
                coverage["complete"] = False
                coverage["reason"] = "per_accession_cap"
            records[accession] = self._annotation_record(queries[accession], selected, coverage)
        return records

    async def _describe_terms(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        """GO ids -> their details via the multi-id ``/ontology/go/terms/{ids}`` endpoint.

        The whole batch is fetched with chunked comma-separated requests (one per
        ``_TERM_CHUNK`` ids) instead of one request per term.
        """
        ids = [str(q.get("go.term", "")).strip() for q in queries]
        distinct = sorted({t for t in ids if t})
        terms: dict[str, dict[str, Any]] = {}
        try:
            for start in range(0, len(distinct), _TERM_CHUNK):
                chunk = distinct[start : start + _TERM_CHUNK]
                if not chunk:
                    continue
                resp = await self._http().get(f"/ontology/go/terms/{','.join(chunk)}")
                resp.raise_for_status()
                for t in resp.json().get("results") or []:
                    if t.get("id"):
                        terms[t["id"]] = t
        except httpx.HTTPStatusError as exc:
            if not is_not_found_status(exc.response.status_code):
                logger.warning("QuickGO term detail failed: %s", exc)
                err = f"QuickGO API error: {format_exc(exc)}"
                return [LookupRecord(query=q, error=err) for q in queries]
        except httpx.HTTPError as exc:
            logger.warning("QuickGO term detail failed: %s", exc)
            err = f"QuickGO API error: {format_exc(exc)}"
            return [LookupRecord(query=q, error=err) for q in queries]

        records: list[LookupRecord] = []
        for query, term_id in zip(queries, ids):
            term = terms.get(term_id) if term_id else None
            if term is None:
                records.append(LookupRecord(query=query, found=False))
            else:
                records.append(LookupRecord(query=query, found=True, values=_describe(term)))
        return records

    async def _resolve_one(self, query: dict[str, Any], accession: str) -> LookupRecord:
        if not accession:
            return LookupRecord(query=query, found=False)
        try:
            rows, coverage = await self._all_annotations(accession)
        except httpx.HTTPStatusError as exc:
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("QuickGO lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"QuickGO API error: {format_exc(exc)}")
        except httpx.HTTPError as exc:  # network/HTTP problem is a per-entity error
            logger.warning("QuickGO lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"QuickGO API error: {format_exc(exc)}")

        return self._annotation_record(query, rows, coverage)

    @staticmethod
    def _annotation_record(
        query: dict[str, Any],
        rows: list[dict[str, Any]],
        coverage: dict[str, Any],
    ) -> LookupRecord:
        if not rows:
            if coverage["complete"] is not True:
                return LookupRecord(
                    query=query,
                    error=(
                        "QuickGO annotation coverage incomplete or unknown before any rows "
                        "for this accession were retrieved"
                    ),
                )
            return LookupRecord(query=query, found=False)
        values = _aggregate(rows)
        values["go.annotation.records"] = sorted(
            [dict(row) for row in rows],
            key=lambda row: (
                row.get("goId") or "",
                row.get("id") or "",
                json.dumps(row, sort_keys=True),
            ),
        )
        values["go.annotation.coverage"] = coverage
        warnings = ()
        if coverage["complete"] is not True:
            state = "incomplete" if coverage["complete"] is False else "unknown"
            warnings = (
                (
                    f"QuickGO annotation coverage {state}: {coverage['reason']}; "
                    "go.count describes only the retrieved term inventory"
                ),
            )
        return LookupRecord(query=query, found=True, values=values, warnings=warnings)

    async def _all_annotations(
        self,
        accession: str,
        *,
        max_pages: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Collect bounded pages, retaining the source's pagination/accounting claims."""
        rows: list[dict[str, Any]] = []
        total_pages: int | None = None
        total_annotations: int | None = None
        complete: bool | None = None
        reason: str | None = None
        pages_retrieved = 0
        page_cap = max_pages if max_pages is not None else self._max_pages
        for page in range(1, page_cap + 1):
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
            rows.extend(body.get("results") or [])
            pages_retrieved = page
            reported_pages = (body.get("pageInfo") or {}).get("total")
            reported_hits = body.get("numberOfHits")
            if isinstance(reported_hits, int) and not isinstance(reported_hits, bool):
                total_annotations = reported_hits
            if not isinstance(reported_pages, int) or isinstance(reported_pages, bool):
                reason = "missing_page_info"
                break
            total_pages = reported_pages
            if page >= total_pages:
                complete = True
                if total_annotations is not None and len(rows) != total_annotations:
                    complete = False
                    reason = "row_count_mismatch"
                break
        else:
            complete = False
            reason = "page_cap"
            logger.info("QuickGO annotations for %s truncated at %d pages", accession, page_cap)
        return rows, {
            "complete": complete,
            "reason": reason,
            "pages_retrieved": pages_retrieved,
            "total_pages": total_pages,
            "total_annotations": total_annotations,
            "observed_annotations": len(rows),
        }
