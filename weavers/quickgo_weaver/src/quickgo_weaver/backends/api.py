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
import re
from copy import deepcopy
from dataclasses import replace
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status, map_bounded
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

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


class _InvalidResponse(ValueError):
    """Expected source schema or correlation failure, rather than a coding fault."""


def _validated_results(body: Any, *, annotation: bool) -> list[dict[str, Any]]:
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise _InvalidResponse("QuickGO response must contain a results list")
    for row in body["results"]:
        key = "goId" if annotation else "id"
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key]:
            raise _InvalidResponse(f"QuickGO row must contain {key}")
        for field in (
            ("goName", "goAspect", "geneProductId", "id") if annotation else ("name", "aspect")
        ):
            if row.get(field) is not None and not isinstance(row[field], str):
                raise _InvalidResponse(f"QuickGO {field} must be a string or null")
        if not annotation:
            definition = row.get("definition")
            if definition is not None and (
                not isinstance(definition, dict)
                or (definition.get("text") is not None and not isinstance(definition["text"], str))
            ):
                raise _InvalidResponse("QuickGO definition must be an object with string text")
    if annotation:
        for row in body["results"]:
            qualifier = row.get("qualifier")
            if qualifier is not None and not (
                isinstance(qualifier, str)
                or isinstance(qualifier, list)
                and all(isinstance(value, str) for value in qualifier)
            ):
                raise _InvalidResponse("QuickGO qualifier must be a string or string list")
        info = body.get("pageInfo")
        if info is not None:
            if not isinstance(info, dict):
                raise _InvalidResponse("QuickGO pageInfo must be an object")
            for key in ("total", "current"):
                value = info.get(key)
                if value is not None and (
                    isinstance(value, bool) or not isinstance(value, int) or value < 0
                ):
                    raise _InvalidResponse(f"QuickGO pageInfo.{key} must be a non-negative integer")
        hits = body.get("numberOfHits")
        if hits is not None and (isinstance(hits, bool) or not isinstance(hits, int) or hits < 0):
            raise _InvalidResponse("QuickGO numberOfHits must be a non-negative integer")
    return body["results"]


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


def _negative(row: dict[str, Any]) -> bool:
    qualifier = row.get("qualifier") or ""
    tokens = qualifier.split("|") if isinstance(qualifier, str) else qualifier
    return "NOT" in tokens


def _relations(term: dict[str, Any]) -> dict[str, Any]:
    children = term.get("children")
    return {
        "id": term["id"],
        "children": sorted(
            [
                {"id": key[0], "relation": key[1]}
                for key in {(child["id"], child["relation"]) for child in children or []}
            ],
            key=lambda child: (child["id"], child["relation"]),
        )
        if children is not None
        else None,
        "is_obsolete": term.get("isObsolete"),
        "parents": None,
        "replacement_ids": None,
        "scope": "observed term children and obsoletion; parents and replacements not acquired",
        "source": deepcopy(term),
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Dedup annotation rows to distinct GO terms and group by aspect (deterministically)."""
    terms: dict[str, dict[str, Any]] = {}
    for row in rows:
        go_id = row.get("goId")
        if _negative(row):
            continue
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


class QuickgoApiBackend(HTTPClientLifecycle, BackendBase):
    """QuickGO REST backend. Always configured — the API is free, no key."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        max_pages: int = _MAX_PAGES,
    ) -> None:
        self._configure_client(client, base_url)
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
            raise ValueError("max_pages must be a positive integer")
        self._max_pages = max_pages

    def is_configured(self) -> bool:
        """QuickGO REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """Identify the effective endpoint and result-affecting policy, not live contents."""
        endpoint = (
            str(self._client.base_url)
            if self._client is not None and str(self._client.base_url)
            else self._base_url
        )
        return remote_fingerprint("quickgo-api", endpoint, max_pages=self._max_pages)

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        self._ensure_open()
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
            records = await self._describe_terms(
                queries, relations="relations" in groups_to_compute
            )
            if "hierarchy" in groups_to_compute:
                return await self._hierarchy(records)
            return records
        options = params or {}
        evidence = options.get("evidence_code")
        usage = options.get("evidence_usage", "exact")
        if (
            evidence is not None
            and (not isinstance(evidence, str) or not re.fullmatch(r"ECO:[0-9]{7}", evidence))
        ) or usage not in {"exact", "descendants"}:
            return [
                LookupRecord(
                    query=q,
                    error="QuickGO evidence_code must be an ECO ID with exact/descendants usage",
                )
                for q in queries
            ]
        filters = {}
        for source, target in [
            ("evidence_code", "evidenceCode"),
            ("qualifier", "qualifier"),
            ("aspect", "aspect"),
        ]:
            if source in options:
                if not isinstance(options[source], str) or not options[source]:
                    return [
                        LookupRecord(query=q, error="QuickGO filters must be nonempty strings")
                        for q in queries
                    ]
                filters[target] = options[source]
        if evidence is not None:
            filters["evidenceCodeUsage"] = usage
        if capability_id == "list_gene_products":
            taxon = options.get("taxon_id")
            if taxon is not None:
                if isinstance(taxon, bool) or not isinstance(taxon, int) or taxon < 1:
                    return [
                        LookupRecord(query=q, error="taxon_id must be a positive integer")
                        for q in queries
                    ]
                filters["taxonId"] = str(taxon)
            filters.update({"goUsage": "exact", "geneProductType": "protein"})
            return await self._reverse_annotations(queries, filters)
        return await self._list_annotations(queries, filters=filters)

    async def _hierarchy(self, records: list[LookupRecord]) -> list[LookupRecord]:
        async def acquire(record):
            if not record.found or record.error:
                return record
            term_id = record.query.get("go.term")
            try:
                complete, ancestors = [], []
                for suffix, target in [("complete", complete), ("ancestors", ancestors)]:
                    response = await self._http().get(f"/ontology/go/terms/{term_id}/{suffix}")
                    response.raise_for_status()
                    target.extend(_validated_results(response.json(), annotation=False))
                if (
                    len(complete) != 1
                    or len(ancestors) != 1
                    or any(row["id"] != term_id for row in complete + ancestors)
                ):
                    raise _InvalidResponse("QuickGO hierarchy identity mismatch")
                term = complete[0]
                ancestor_ids = ancestors[0].get("ancestors")
                if ancestor_ids is not None and (
                    not isinstance(ancestor_ids, list)
                    or any(not isinstance(x, str) for x in ancestor_ids)
                ):
                    raise _InvalidResponse("QuickGO ancestors must be identifiers")
                response = await self._http().get(
                    f"/ontology/go/terms/{term_id}/paths/GO:0008150,GO:0003674,GO:0005575",
                    params={"relations": "is_a,part_of"},
                )
                response.raise_for_status()
                paths = response.json().get("results")
                if not isinstance(paths, list) or any(not isinstance(path, list) for path in paths):
                    raise _InvalidResponse("QuickGO paths must be lists")
                parents = set()
                for path in paths:
                    for edge in path:
                        if not isinstance(edge, dict) or any(
                            not isinstance(edge.get(key), str)
                            for key in ("child", "parent", "relationship")
                        ):
                            raise _InvalidResponse("QuickGO paths need typed edges")
                        if edge["child"] == term_id:
                            parents.add((edge["parent"], edge["relationship"]))
                for field in ("replacements", "replaces"):
                    value = term.get(field)
                    if value is not None and (
                        not isinstance(value, list)
                        or any(
                            not isinstance(row, dict)
                            or not isinstance(row.get("id"), str)
                            or not isinstance(row.get("type"), str)
                            for row in value
                        )
                    ):
                        raise _InvalidResponse("QuickGO replacement history needs typed records")
                values = deepcopy(record.values)
                values["go.term.hierarchy"] = {
                    "id": term_id,
                    "parents": [
                        {"id": identifier, "relation": relation}
                        for identifier, relation in sorted(parents)
                    ],
                    "parent_scope": "observed is_a/part_of paths to the three GO aspect roots",
                    "ancestors": sorted(set(ancestor_ids)) if ancestor_ids is not None else None,
                    "ancestor_scope": "provider ancestor endpoint default relations, including self",
                    "replacements": term.get("replacements"),
                    "replaces": term.get("replaces"),
                    "history": term.get("history"),
                    "is_obsolete": term.get("isObsolete"),
                    "paths": paths,
                    "source": "QuickGO complete, ancestors and paths endpoints",
                }
                return replace(record, values=values)
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                return LookupRecord(
                    query=record.query, error=f"QuickGO hierarchy error: {format_exc(exc)}"
                )

        distinct = {str(record.query.get("go.term")): record for record in records}
        results = await map_bounded(list(distinct.values()), acquire, limit=4)
        by_id = dict(zip(distinct, results))
        return [
            replace(
                by_id[str(record.query.get("go.term"))],
                query=record.query,
                values=deepcopy(by_id[str(record.query.get("go.term"))].values),
            )
            for record in records
        ]

    async def _reverse_annotations(self, queries, filters):
        ids = [str(q.get("go.term", "")).strip() for q in queries]
        records = {}
        distinct = sorted(set(ids) - {""})
        for start in range(0, len(distinct), _ACCESSION_CHUNK):
            chunk = distinct[start : start + _ACCESSION_CHUNK]
            try:
                rows, coverage = await self._all_annotations(
                    ",".join(chunk), filters=filters, reverse=True
                )
                for term_id in chunk:
                    selected = [row for row in rows if row["goId"] == term_id]
                    products = sorted(
                        {
                            row["geneProductId"].split(":", 1)[1]
                            for row in selected
                            if not _negative(row) and row["geneProductId"].startswith("UniProtKB:")
                        }
                    )
                    if not selected and coverage["complete"] is True:
                        records[term_id] = LookupRecord(query={}, found=False)
                    elif not selected:
                        records[term_id] = LookupRecord(query={}, error="QuickGO reverse coverage incomplete before any annotations for this term were retrieved")
                    else:
                        values = {
                            "protein.uniprot.accession": products,
                            "go.reverse.annotations": deepcopy(selected),
                            "go.reverse.coverage": {
                                **coverage,
                                "query_scope": chunk,
                                "observed_products": len(products),
                                "count_scope": "retrieved positive UniProtKB products; source totals count annotations",
                            },
                        }
                        warnings = (
                            ()
                            if coverage["complete"] is True
                            else ("QuickGO reverse annotation coverage incomplete or unknown",)
                        )
                        records[term_id] = LookupRecord(
                            query={}, found=True, values=values, warnings=warnings
                        )
            except httpx.HTTPStatusError as exc:
                records.update(
                    {
                        term_id: LookupRecord(query={}, found=False)
                        if is_not_found_status(exc.response.status_code)
                        else LookupRecord(query={}, error=f"QuickGO API error: {format_exc(exc)}")
                        for term_id in chunk
                    }
                )
            except (httpx.HTTPError, ValueError, _InvalidResponse) as exc:
                records.update(
                    {
                        term_id: LookupRecord(
                            query={}, error=f"QuickGO API error: {format_exc(exc)}"
                        )
                        for term_id in chunk
                    }
                )
        return [
            replace(records[term_id], query=query, values=deepcopy(records[term_id].values))
            if term_id
            else LookupRecord(query=query, found=False)
            for query, term_id in zip(queries, ids)
        ]

    async def _list_annotations(
        self, queries: list[dict[str, Any]], *, filters: dict[str, str] | None = None
    ) -> list[LookupRecord]:
        ids = [str(q.get("protein.uniprot.accession", "")).strip().upper() for q in queries]
        distinct = sorted({accession for accession in ids if accession})
        by_id: dict[str, LookupRecord] = {}
        for start in range(0, len(distinct), _ACCESSION_CHUNK):
            chunk = distinct[start : start + _ACCESSION_CHUNK]
            if len(chunk) == 1:
                query = {"protein.uniprot.accession": chunk[0]}
                by_id[chunk[0]] = await self._resolve_one(query, chunk[0], filters=filters)
            else:
                by_id.update(await self._resolve_batch(chunk, filters=filters))
        return [
            replace(by_id[accession], query=query, values=deepcopy(by_id[accession].values))
            if accession
            else LookupRecord(query=query, found=False)
            for query, accession in zip(queries, ids)
        ]

    async def _resolve_batch(
        self, accessions: list[str], *, filters: dict[str, str] | None = None
    ) -> dict[str, LookupRecord]:
        queries = {accession: {"protein.uniprot.accession": accession} for accession in accessions}
        try:
            rows, source_coverage = await self._all_annotations(
                ",".join(accessions),
                max_pages=self._max_pages * len(accessions),
                filters=filters,
            )
        except httpx.HTTPStatusError as exc:
            if is_not_found_status(exc.response.status_code):
                return {a: LookupRecord(query=q, found=False) for a, q in queries.items()}
            return {
                a: LookupRecord(query=q, error=f"QuickGO API error: {format_exc(exc)}")
                for a, q in queries.items()
            }
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError, _InvalidResponse) as exc:
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

    async def _describe_terms(
        self, queries: list[dict[str, Any]], *, relations: bool = False
    ) -> list[LookupRecord]:
        """GO ids -> their details via the multi-id ``/ontology/go/terms/{ids}`` endpoint.

        The whole batch is fetched with chunked comma-separated requests (one per
        ``_TERM_CHUNK`` ids) instead of one request per term.
        """
        ids = [str(q.get("go.term", "")).strip() for q in queries]
        distinct = sorted({t for t in ids if t})
        terms: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        for start in range(0, len(distinct), _TERM_CHUNK):
            chunk = distinct[start : start + _TERM_CHUNK]
            try:
                resp = await self._http().get(f"/ontology/go/terms/{','.join(chunk)}")
                resp.raise_for_status()
                rows = _validated_results(resp.json(), annotation=False)
                if any(row["id"] not in chunk for row in rows):
                    raise _InvalidResponse(
                        "QuickGO term response contains an unrequested identifier"
                    )
                if relations:
                    for row in rows:
                        children = row.get("children")
                        if children is not None and (
                            not isinstance(children, list)
                            or any(
                                not isinstance(child, dict)
                                or not isinstance(child.get("id"), str)
                                or not isinstance(child.get("relation"), str)
                                for child in children
                            )
                        ):
                            raise _InvalidResponse(
                                "QuickGO children must be typed relation objects"
                            )
                terms.update({row["id"]: row for row in rows})
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    errors.update(dict.fromkeys(chunk, f"QuickGO API error: {format_exc(exc)}"))
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                errors.update(dict.fromkeys(chunk, f"QuickGO API error: {format_exc(exc)}"))

        records: list[LookupRecord] = []
        for query, term_id in zip(queries, ids):
            term = terms.get(term_id) if term_id else None
            if term_id in errors:
                records.append(LookupRecord(query=query, error=errors[term_id]))
            elif term is None:
                records.append(LookupRecord(query=query, found=False))
            else:
                values = _describe(term)
                if relations:
                    values["go.term.relations"] = _relations(term)
                records.append(LookupRecord(query=query, found=True, values=values))
        return records

    async def _resolve_one(
        self, query: dict[str, Any], accession: str, *, filters: dict[str, str] | None = None
    ) -> LookupRecord:
        if not accession:
            return LookupRecord(query=query, found=False)
        try:
            rows, coverage = await self._all_annotations(accession, filters=filters)
        except httpx.HTTPStatusError as exc:
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("QuickGO lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"QuickGO API error: {format_exc(exc)}")
        except (
            httpx.HTTPError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            _InvalidResponse,
        ) as exc:  # network/HTTP problem is a per-entity error
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
        coverage = dict(coverage)
        coverage["negative_annotations"] = sum(_negative(row) for row in rows)
        coverage["positive_annotations"] = len(rows) - coverage["negative_annotations"]
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
        filters: dict[str, str] | None = None,
        reverse: bool = False,
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
                    ("goId" if reverse else "geneProductId"): accession,
                    "limit": str(_PAGE_SIZE),
                    "page": str(page),
                    "includeFields": "goName",
                    **(filters or {}),
                },
            )
            resp.raise_for_status()
            body = resp.json()
            page_rows = _validated_results(body, annotation=True)
            expected = set(accession.upper().split(","))
            for row in page_rows:
                scope = filters or {}
                if "aspect" in scope and row.get("goAspect") != scope["aspect"]:
                    raise _InvalidResponse("QuickGO response violates requested aspect")
                if (
                    scope.get("evidenceCodeUsage") == "exact"
                    and row.get("evidenceCode") != scope["evidenceCode"]
                ):
                    raise _InvalidResponse("QuickGO response violates exact ECO evidence filter")
                echo = row.get("geneProductId")
                if not echo or (
                    row["goId"] not in expected
                    if reverse
                    else echo.rsplit(":", 1)[-1].upper() not in expected
                ):
                    raise _InvalidResponse(
                        "QuickGO response cannot be correlated to requested accession"
                    )
            rows.extend(page_rows)
            pages_retrieved = page
            info = body.get("pageInfo") or {}
            # Live QuickGO uses current=total=0 for a genuine empty result.
            empty_page = not page_rows and body.get("numberOfHits") == 0 and info.get("total") == 0
            if info.get("current") is not None and info["current"] != page and not empty_page:
                raise _InvalidResponse("QuickGO response echoes a different page")
            reported_pages = info.get("total")
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
            "filters": dict(filters or {}),
            "summary_scope": "positive annotations only; NOT records retained in raw evidence",
            "reason": reason,
            "pages_retrieved": pages_retrieved,
            "total_pages": total_pages,
            "total_annotations": total_annotations,
            "observed_annotations": len(rows),
        }
