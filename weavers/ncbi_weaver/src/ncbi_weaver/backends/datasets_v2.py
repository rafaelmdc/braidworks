"""DatasetsV2Backend — NCBI Datasets v2 REST taxonomy backend.

Strategy:
  * exact: one batched POST to ``taxonomy/dataset_report`` (<=1000 taxons). Each
    ``reports[]`` entry echoes its ``query`` and carries a ``taxonomy`` node
    (tax_id, current_scientific_name.name, rank, parents taxids).
  * fuzzy: queries with no exact node fall back to per-name
    ``taxonomy/taxon_suggest`` (exact_match=false) for suggestions.
  * lineage: Datasets returns ancestry as taxids only; a second batched
    ``dataset_report`` over the deduped union of ancestor taxids resolves their
    names/ranks so the lineage strand matches the local backend's shape.
  * confidence: Datasets gives no numeric score, so matches are re-scored with
    RapidFuzz (query vs. matched name) for parity with the local backend.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport``. Node parsing goes through ``_node_name`` / ``_node_parents``
/ ``_node_rank``, which tolerate both the current schema (``reports`` +
``current_scientific_name`` + ``parents``) and the older one (``taxonomy_nodes`` +
``organism_name`` + ``lineage``). Confirm shapes with the live E2E
(``BRAIDWORKS_RUN_LIVE=1``) after API-touching changes.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import replace
from typing import Any

import httpx
from braidworks.core import LookupRecord, format_exc, is_not_found_status, map_bounded
from braidworks.core.exceptions import BackendConfigurationError
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint
from rapidfuzz import fuzz

from .. import vocab
from ..intermediate import CandidateMatch, LineageEntry, TaxonMatch, TaxonMatchStatus

_CHILDREN_LIMIT = 200  # top-N children surfaced in records (ids/count stay the true total)

logger = logging.getLogger("ncbi_weaver.api")

DEFAULT_BASE_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2"
_PAGE_LIMIT = 1000
_GENE_ID_CHUNK = 250  # gene ids per multi-id dataset_report URL (keeps the path bounded)
_ACC_CHUNK = 100  # genome accessions per multi-id dataset_report URL
_SYMBOL_CHUNK = 100  # gene symbols per multi-symbol dataset_report URL


class _InvalidResponse(ValueError):
    """Malformed NCBI data or response correlation, rather than a programming fault."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _InvalidResponse(f"NCBI {label} must be an object")
    return value


def _objects(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise _InvalidResponse(f"NCBI {label} must be an object list")
    return value


def _identifier(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).isdigit():
        raise _InvalidResponse("NCBI identifier must be a positive integer")
    try:
        result = int(value)
    except ValueError as exc:
        raise _InvalidResponse("NCBI identifier is too large") from exc
    if result < 1:
        raise _InvalidResponse("NCBI identifier must be positive")
    return result


def _validate_node(node: Any) -> None:
    node = _object(node, "taxonomy node")
    _identifier(node.get("tax_id"))
    for field in ("rank", "organism_name"):
        if node.get(field) is not None and not isinstance(node[field], str):
            raise _InvalidResponse(f"NCBI {field} must be a string")
    if node.get("current_scientific_name") is not None:
        name = _object(node["current_scientific_name"], "scientific name").get("name")
        if name is not None and not isinstance(name, str):
            raise _InvalidResponse("NCBI scientific name must be a string")
    parents = node.get("parents", node.get("lineage", []))
    if parents is not None:
        if not isinstance(parents, list):
            raise _InvalidResponse("NCBI parents must be an identifier list")
        for parent in parents:
            _identifier(parent)


def _report_payload(resp: httpx.Response, kind: str) -> dict[str, Any]:
    body = _object(resp.json(), "response")
    key = (
        "taxonomy_nodes"
        if kind == "taxonomy" and "reports" not in body and "taxonomy_nodes" in body
        else "reports"
    )
    rows = _objects(body.get(key), key)
    token = body.get("next_page_token")
    if token is not None and not isinstance(token, str):
        raise _InvalidResponse("NCBI next_page_token must be a string")
    for row in rows:
        if kind == "taxonomy":
            if row.get("taxonomy") is not None:
                _validate_node(row["taxonomy"])
            else:
                errors = _objects(row.get("errors"), "taxonomy errors")
                if not errors or any(
                    not isinstance(error.get("invalid_identifiers"), list)
                    or not error["invalid_identifiers"]
                    for error in errors
                ):
                    raise _InvalidResponse(
                        "NCBI taxonomy report lacks node or explicit invalid-identifier absence"
                    )
            if row.get("query") is not None and (
                not isinstance(row["query"], list)
                or any(not isinstance(q, (str, int)) or isinstance(q, bool) for q in row["query"])
            ):
                raise _InvalidResponse("NCBI query must be an identifier list")
        elif kind == "genome":
            if not isinstance(row.get("accession"), str) or not row["accession"]:
                raise _InvalidResponse("NCBI genome report must contain accession")
            for field in ("assembly_info", "assembly_stats", "annotation_info", "organism"):
                if row.get(field) is not None:
                    _object(row[field], field)
            if (row.get("annotation_info") or {}).get("stats") is not None:
                _object(row["annotation_info"]["stats"], "annotation stats")
        elif kind == "gene":
            gene = _object(row.get("gene"), "gene")
            _identifier(gene.get("gene_id"))
            for field in ("symbol", "description", "type", "taxname"):
                if gene.get(field) is not None and not isinstance(gene[field], str):
                    raise _InvalidResponse(f"NCBI gene {field} must be a string")
            if row.get("query") is not None and (
                not isinstance(row["query"], list)
                or any(not isinstance(q, str) for q in row["query"])
            ):
                raise _InvalidResponse("NCBI gene query must be a string list")
        elif kind == "product":
            product = _object(row.get("product"), "product")
            for transcript in _objects(product.get("transcripts", []), "transcripts"):
                if transcript.get("protein") is not None:
                    _object(transcript["protein"], "protein")
    return body


async def _enrich(
    fetcher: Callable[[str], Awaitable[list[dict[str, Any]]]],
    identifiers: list[str],
    *,
    limit: int = 4,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Isolate expected enrichment failures; propagate cancellation and coding faults."""

    async def one(identifier):
        try:
            return identifier, await fetcher(identifier), None
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError, _InvalidResponse) as exc:
            return identifier, None, format_exc(exc)

    fetched = await map_bounded(list(dict.fromkeys(identifiers)), one, limit=limit)
    return (
        {key: value for key, value, error in fetched if error is None},
        {key: error for key, value, error in fetched if error is not None},
    )


def _node_name(node: dict[str, Any]) -> str | None:
    """Scientific name of a taxonomy node, tolerant of both Datasets v2 shapes.

    Current schema nests it under ``current_scientific_name.name``; older responses
    exposed a flat ``organism_name``.
    """
    csn = node.get("current_scientific_name")
    if isinstance(csn, dict):
        return csn.get("name")
    return node.get("organism_name")


def _node_parents(node: dict[str, Any]) -> list[int]:
    """Ancestor taxids (root → immediate parent), tolerant of both shapes.

    Current schema calls this ``parents``; older responses used ``lineage``.
    """
    raw = node.get("parents")
    if raw is None:
        raw = node.get("lineage")
    return [int(t) for t in raw or []]


def _node_rank(node: dict[str, Any]) -> str | None:
    """Rank, lowercased for parity with the local backend (the API now upper-cases)."""
    rank = node.get("rank")
    return rank.lower() if isinstance(rank, str) else rank


class _PageGuard:
    """Bound one report traversal; interrupted acquisition must not become absence."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.seen: set[str | None] = set()

    def check(self, token: str | None) -> None:
        if token in self.seen or len(self.seen) >= self.limit:
            raise _InvalidResponse(
                f"incomplete report acquisition: pages={len(self.seen)}, "
                f"limit={self.limit}, complete=false; repeated token or page budget"
            )
        self.seen.add(token)

    def check_response(self, response: httpx.Response) -> None:
        if len(self.seen) > 1 and is_not_found_status(response.status_code):
            raise _InvalidResponse(
                "incomplete report acquisition: continuation page unavailable; complete=false"
            )
        response.raise_for_status()


def _rescore(query: str, name: str | None) -> float:
    """RapidFuzz token-set ratio on the 0..100 scale, matching the local fuzzy scale."""
    if not name:
        return 0.0
    return float(fuzz.token_set_ratio(query.lower(), name.lower()))


class DatasetsV2Backend(HTTPClientLifecycle):
    """Resolution backend backed by the NCBI Datasets v2 REST API."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        allow_fuzzy: bool = True,
        max_report_pages: int = 1000,
        max_concurrency: int = 4,
    ) -> None:
        self._configure_client(client, base_url)
        if client is not None and api_key is not None and client.headers.get("api-key") != api_key:
            raise BackendConfigurationError("Set api-key on the injected client or omit api_key")
        self._api_key = api_key
        self._allow_fuzzy = allow_fuzzy
        if (
            isinstance(max_report_pages, bool)
            or not isinstance(max_report_pages, int)
            or max_report_pages < 1
        ):
            raise ValueError("max_report_pages must be a positive integer")
        self._max_report_pages = max_report_pages
        if (
            isinstance(max_concurrency, bool)
            or not isinstance(max_concurrency, int)
            or max_concurrency < 1
        ):
            raise ValueError("max_concurrency must be a positive integer")
        self._max_concurrency = max_concurrency

    def is_configured(self) -> bool:
        """The API backend is always usable; it needs no local data."""
        return True

    def fingerprint(self) -> str:
        """Datasets v2 is a live service, so the fingerprint is a fixed identifier."""
        return remote_fingerprint(
            "ncbi_weaver-api",
            self._base_url,
            contract=f"datasets-v2:pages={self._max_report_pages}",
            allow_fuzzy=self._allow_fuzzy,
        )

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        """Return the HTTP client, lazily creating one if none was injected."""
        self._ensure_open()
        if self._client is None:
            headers = {"api-key": self._api_key} if self._api_key else {}
            self._client = httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=30.0)
        return PacedHTTPClient(self._client, "ncbi", default_rate=5.0)

    async def resolve(
        self, capability_id: str, queries: list, *, need_lineage: bool
    ) -> list[TaxonMatch]:
        """Resolve a batch: exact via dataset_report, fuzzy via taxon_suggest."""
        if capability_id not in (vocab.RESOLVE_NAME, vocab.DESCRIBE_TAXON):
            raise ValueError(f"unsupported capability {capability_id!r}")
        queries = [str(q) for q in queries]
        logger.info(
            "resolving %d quer%s via NCBI Datasets v2 over the network (%s)",
            len(queries),
            "y" if len(queries) == 1 else "ies",
            self._base_url,
        )
        matches: dict[str, TaxonMatch] = {}
        fuzzy_queries: list[str] = []
        distinct = sorted({query for query in queries if query.strip()})
        for q in queries:
            if not q.strip():
                matches[q] = TaxonMatch(query=q, status=TaxonMatchStatus.NO_MATCH)
        for start in range(0, len(distinct), _PAGE_LIMIT):
            chunk = distinct[start : start + _PAGE_LIMIT]
            try:
                nodes = await self._dataset_report(chunk)
            except httpx.HTTPStatusError as exc:
                status = (
                    TaxonMatchStatus.NO_MATCH
                    if is_not_found_status(exc.response.status_code)
                    else TaxonMatchStatus.ERROR
                )
                for q in chunk:
                    matches[q] = TaxonMatch(
                        query=q,
                        status=status,
                        error=None
                        if status is TaxonMatchStatus.NO_MATCH
                        else f"NCBI taxonomy error: {format_exc(exc)}",
                    )
                continue
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                for q in chunk:
                    matches[q] = TaxonMatch(
                        query=q,
                        status=TaxonMatchStatus.ERROR,
                        error=f"NCBI taxonomy error: {format_exc(exc)}",
                    )
                continue
            for q in chunk:
                node = nodes.get(q)
                if node is not None:
                    matches[q] = self._node_match(q, node, match_type="exact")
                elif capability_id == vocab.RESOLVE_NAME and self._allow_fuzzy:
                    fuzzy_queries.append(q)
                else:
                    matches[q] = TaxonMatch(query=q, status=TaxonMatchStatus.NO_MATCH)

        async def fuzzy_one(q):
            try:
                return await self._fuzzy_match(q)
            except httpx.HTTPStatusError as exc:
                status = (
                    TaxonMatchStatus.NO_MATCH
                    if is_not_found_status(exc.response.status_code)
                    else TaxonMatchStatus.ERROR
                )
                return TaxonMatch(
                    query=q,
                    status=status,
                    error=None
                    if status is TaxonMatchStatus.NO_MATCH
                    else f"NCBI suggestion error: {format_exc(exc)}",
                )
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                return TaxonMatch(
                    query=q,
                    status=TaxonMatchStatus.ERROR,
                    error=f"NCBI suggestion error: {format_exc(exc)}",
                )

        fuzzy_matches = await map_bounded(fuzzy_queries, fuzzy_one, limit=self._max_concurrency)
        matches.update(zip(fuzzy_queries, fuzzy_matches))

        if need_lineage:
            await self._attach_lineage(matches)

        # Preserve input order (queries may contain duplicates → reuse the match).
        return [matches[q] for q in queries]

    async def _distinct_queries(
        self,
        queries: list[dict[str, Any]],
        key: str,
        operation: Callable[[dict[str, Any]], Awaitable[LookupRecord]],
    ) -> list[LookupRecord]:
        """Share source work by normalized identifier; preserve each caller's query."""
        keys = [str(q.get(key, "") or "").strip() for q in queries]
        representatives = dict(zip(keys, queries))
        distinct = list(representatives)

        async def one(identifier):
            return await operation(representatives[identifier])

        records = await map_bounded(distinct, one, limit=self._max_concurrency)
        by_key = dict(zip(distinct, records))
        return [
            replace(by_key[key], query=q, values=deepcopy(by_key[key].values))
            for key, q in zip(keys, queries)
        ]

    async def list_children(
        self, queries: list[dict[str, Any]], *, rank: str
    ) -> list[LookupRecord]:
        """One taxid -> its descendant taxids of ``rank`` (walks the subtree)."""
        rank_norm = (rank or "species").strip().lower()

        async def one(q):
            taxid = str(q.get(vocab.TAXON_ID, "") or "").strip()
            if not taxid:
                return LookupRecord(query=q, found=False)
            try:
                children = await self._fetch_children(taxid, rank_norm)
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    return LookupRecord(query=q, found=False)
                logger.warning("NCBI children failed for %r: %s", taxid, exc)
                return LookupRecord(query=q, error=f"NCBI children error: {format_exc(exc)}")
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                logger.warning("NCBI children failed for %r: %s", taxid, exc)
                return LookupRecord(query=q, error=f"NCBI children error: {format_exc(exc)}")
            if not children:
                return LookupRecord(query=q, found=False)
            ids = [c["taxid"] for c in children]
            return LookupRecord(
                query=q,
                found=True,
                values={
                    vocab.TAXON_ID: ids,
                    vocab.CHILDREN_COUNT: len(ids),
                    vocab.CHILDREN_RECORDS: children[:_CHILDREN_LIMIT],
                },
            )

        return await self._distinct_queries(queries, vocab.TAXON_ID, one)

    async def _fetch_children(self, taxid: str, rank: str) -> list[dict[str, Any]]:
        """Walk dataset_report?children=true, keep distinct descendants of ``rank``."""
        out: dict[int, dict[str, Any]] = {}
        page_token: str | None = None
        guard = _PageGuard(self._max_report_pages)
        while True:
            guard.check(page_token)
            params: dict[str, Any] = {"children": "true", "page_size": 1000}
            if page_token:
                params["page_token"] = page_token
            resp = await self._http().get(f"/taxonomy/taxon/{taxid}/dataset_report", params=params)
            guard.check_response(resp)
            body = _report_payload(resp, "taxonomy")
            for entry in body.get("reports") or []:
                node = entry.get("taxonomy") or {}
                tid = _identifier(node.get("tax_id"))
                if tid is None or str(tid) == taxid:
                    continue  # skip the queried node itself
                if rank and (node.get("rank") or "").lower() != rank:
                    continue
                if tid not in out:
                    out[tid] = {
                        "taxid": tid,
                        "name": _node_name(node),
                        "rank": (node.get("rank") or "").lower(),
                    }
            page_token = body.get("next_page_token")
            if not page_token:
                break
        # Deterministic order: ascending taxid.
        return [out[k] for k in sorted(out)]

    # --- genome capabilities ------------------------------------------------

    async def list_genomes(
        self,
        queries: list[dict[str, Any]],
        *,
        reference_only: bool = False,
        annotated_only: bool = False,
        assembly_level: str | None = None,
    ) -> list[LookupRecord]:
        """One taxid -> its genome assembly accessions, filtered per the parameters."""
        params: dict[str, Any] = {"page_size": 1000}
        if reference_only:
            params["filters.reference_only"] = "true"
        if annotated_only:
            params["filters.has_annotation"] = "true"
        if assembly_level:
            params["filters.assembly_level"] = assembly_level

        async def one(q):
            taxid = str(q.get(vocab.TAXON_ID, "") or "").strip()
            if not taxid:
                return LookupRecord(query=q, found=False)
            try:
                assemblies = await self._fetch_genomes(taxid, params)
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    return LookupRecord(query=q, found=False)
                return LookupRecord(query=q, error=f"NCBI genomes error: {format_exc(exc)}")
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                return LookupRecord(query=q, error=f"NCBI genomes error: {format_exc(exc)}")
            if not assemblies:
                return LookupRecord(query=q, found=False)
            return LookupRecord(
                query=q,
                found=True,
                values={
                    vocab.GENOME_ACCESSION: [a["accession"] for a in assemblies],
                    vocab.ASSEMBLY_COUNT: len(assemblies),
                    vocab.ASSEMBLY_RECORDS: assemblies[:_CHILDREN_LIMIT],
                },
            )

        return await self._distinct_queries(queries, vocab.TAXON_ID, one)

    async def _fetch_genomes(self, taxid: str, base_params: dict) -> list[dict[str, Any]]:
        """Paginate genome/taxon/{taxid}/dataset_report into compact assembly rows."""
        out: dict[str, dict[str, Any]] = {}
        page_token: str | None = None
        guard = _PageGuard(self._max_report_pages)
        while True:
            guard.check(page_token)
            params = dict(base_params)
            if page_token:
                params["page_token"] = page_token
            resp = await self._http().get(f"/genome/taxon/{taxid}/dataset_report", params=params)
            guard.check_response(resp)
            body = _report_payload(resp, "genome")
            for a in body.get("reports") or []:
                acc = a.get("accession")
                if not acc or acc in out:
                    continue
                info = a.get("assembly_info") or {}
                org = a.get("organism") or {}
                out[acc] = {
                    "accession": acc,
                    "organism": org.get("organism_name"),
                    "tax_id": org.get("tax_id"),
                    "assembly_level": info.get("assembly_level"),
                    "assembly_name": info.get("assembly_name"),
                    "refseq_category": info.get("refseq_category"),
                    "release_date": info.get("release_date"),
                }
            page_token = body.get("next_page_token")
            if not page_token:
                break
        # Deterministic: accession ascending.
        return [out[k] for k in sorted(out)]

    async def describe_genome(
        self, queries: list[dict[str, Any]], *, groups: frozenset[str]
    ) -> list[LookupRecord]:
        """Genome accessions -> assembly detail (+ sequences if that group was asked).

        Assembly reports for the whole batch are fetched with chunked multi-accession
        ``dataset_report`` requests; per-sequence reports — a genuinely per-accession
        endpoint — are then fetched concurrently.
        """
        want_sequences = "sequences" in groups
        accs = [str(q.get(vocab.GENOME_ACCESSION, "") or "").strip() for q in queries]
        distinct = sorted({a for a in accs if a})
        reports: dict[str, dict[str, Any]] = {}
        source_errors: dict[str, str] = {}
        for start in range(0, len(distinct), _ACC_CHUNK):
            chunk = distinct[start : start + _ACC_CHUNK]
            try:
                reports.update(await self._genome_reports(chunk))
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    source_errors.update(
                        dict.fromkeys(chunk, f"NCBI report error: {format_exc(exc)}")
                    )
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                source_errors.update(dict.fromkeys(chunk, f"NCBI report error: {format_exc(exc)}"))

        sequences: dict[str, list[dict[str, Any]]] = {}
        enrichment_errors: dict[str, str] = {}
        if want_sequences:
            found = [a for a in distinct if a in reports]
            sequences, enrichment_errors = await _enrich(
                self._fetch_sequences, found, limit=self._max_concurrency
            )

        records: list[LookupRecord] = []
        for q, acc in zip(queries, accs):
            if acc in source_errors:
                records.append(LookupRecord(query=q, error=source_errors[acc]))
                continue
            report = reports.get(acc) if acc else None
            if report is None:
                records.append(LookupRecord(query=q, found=False))
                continue
            if acc in enrichment_errors:
                records.append(
                    LookupRecord(query=q, error=f"NCBI sequences error: {enrichment_errors[acc]}")
                )
                continue
            values = self._genome_values(report)
            if want_sequences and acc in sequences:
                values[vocab.SEQUENCE_RECORDS] = sequences[acc]
                values[vocab.SEQUENCE_COVERAGE] = {
                    "complete": True,
                    "observed_records": len(sequences[acc]),
                    "returned_records": len(sequences[acc]),
                    "scope": "sequence_reports",
                }
            records.append(LookupRecord(query=q, found=True, values=values))
        return records

    async def _genome_reports(self, accs: list[str]) -> dict[str, dict[str, Any]]:
        """Batch-fetch assembly reports by accession, keyed by ``accession`` (the genome
        analogue of :meth:`_dataset_report`).

        Hits the multi-accession ``genome/accession/{accs}/dataset_report`` endpoint,
        chunked and paginated — one request per chunk instead of one per accession.
        """
        out: dict[str, dict[str, Any]] = {}
        for start in range(0, len(accs), _ACC_CHUNK):
            chunk = accs[start : start + _ACC_CHUNK]
            if not chunk:
                continue
            page_token: str | None = None
            guard = _PageGuard(self._max_report_pages)
            while True:
                guard.check(page_token)
                params: dict[str, Any] = {"page_size": _PAGE_LIMIT}
                if page_token:
                    params["page_token"] = page_token
                resp = await self._http().get(
                    f"/genome/accession/{','.join(chunk)}/dataset_report", params=params
                )
                guard.check_response(resp)
                body = _report_payload(resp, "genome")
                for a in body.get("reports") or []:
                    acc = a.get("accession")
                    if acc not in chunk:
                        raise _InvalidResponse(
                            "NCBI genome response contains unrequested accession"
                        )
                    out[acc] = a
                page_token = body.get("next_page_token")
                if not page_token:
                    break
        return out

    @staticmethod
    def _genome_values(a: dict[str, Any]) -> dict[str, Any]:
        """One assembly dataset_report entry -> describe_genome assembly outputs."""
        info = a.get("assembly_info") or {}
        stats = a.get("assembly_stats") or {}
        ann = a.get("annotation_info") or {}
        org = a.get("organism") or {}
        values: dict[str, Any] = {
            vocab.ASSEMBLY_TITLE: info.get("assembly_name"),
            vocab.ASSEMBLY_LEVEL: info.get("assembly_level"),
            vocab.ASSEMBLY_ORGANISM: org.get("organism_name"),
            vocab.ASSEMBLY_DETAIL: {
                "accession": a.get("accession"),
                "assembly_name": info.get("assembly_name"),
                "assembly_level": info.get("assembly_level"),
                "submitter": info.get("submitter"),
                "release_date": info.get("release_date"),
                "refseq_category": info.get("refseq_category"),
                "organism": org.get("organism_name"),
                "tax_id": org.get("tax_id"),
                "total_sequence_length": stats.get("total_sequence_length"),
                "gc_percent": stats.get("gc_percent"),
                "contig_n50": stats.get("contig_n50"),
                "gene_counts": (ann.get("stats") or {}).get("gene_counts"),
            },
        }
        return values

    async def _fetch_sequences(self, acc: str) -> list[dict[str, Any]]:
        """Per-sequence reports for an assembly (chromosomes/plasmids/contigs)."""
        out: list[dict[str, Any]] = []
        page_token: str | None = None
        guard = _PageGuard(self._max_report_pages)
        while True:
            guard.check(page_token)
            params: dict[str, Any] = {"page_size": 1000}
            if page_token:
                params["page_token"] = page_token
            resp = await self._http().get(
                f"/genome/accession/{acc}/sequence_reports", params=params
            )
            guard.check_response(resp)
            body = _report_payload(resp, "sequence")
            for s in body.get("reports") or []:
                out.append(
                    {
                        "name": s.get("chr_name") or s.get("sequence_name"),
                        "role": s.get("role"),
                        "length": s.get("length"),
                        "refseq_accession": s.get("refseq_accession"),
                        "genbank_accession": s.get("genbank_accession"),
                    }
                )
            page_token = body.get("next_page_token")
            if not page_token:
                break
        return out

    # --- gene capabilities --------------------------------------------------

    @staticmethod
    def _gene_summary(g: dict[str, Any]) -> dict[str, Any]:
        return {
            vocab.GENE_SYMBOL: g.get("symbol"),
            vocab.GENE_NAME: g.get("description"),
            vocab.GENE_TYPE: g.get("type"),
            vocab.GENE_ORGANISM: g.get("taxname"),
            vocab.GENE_DETAIL: {
                "gene_id": g.get("gene_id"),
                "symbol": g.get("symbol"),
                "description": g.get("description"),
                "type": g.get("type"),
                "taxname": g.get("taxname"),
                "tax_id": g.get("tax_id"),
                "chromosomes": g.get("chromosomes"),
                "synonyms": g.get("synonyms"),
                "ensembl_gene_ids": g.get("ensembl_gene_ids"),
                "swiss_prot_accessions": g.get("swiss_prot_accessions"),
                "transcript_count": g.get("transcript_count"),
                "protein_count": g.get("protein_count"),
            },
        }

    async def resolve_gene(
        self, queries: list[dict[str, Any]], *, taxon: str
    ) -> list[LookupRecord]:
        """Gene symbols (in ``taxon``) -> their NCBI gene ids + summaries.

        All symbols in the batch share one ``taxon`` (a per-call param), so the whole
        batch is resolved with chunked multi-symbol ``dataset_report`` requests instead
        of one request per symbol. Each report echoes its input ``query``, so results map
        back to the requested symbol even when NCBI resolves an alias to a different
        official symbol.
        """
        tx = (taxon or "9606").strip()
        symbols = [str(q.get(vocab.PROTEIN_QUERY, "") or "").strip() for q in queries]
        distinct = sorted({s for s in symbols if s})
        by_symbol: dict[str, dict[str, dict[str, Any]]] = {}
        errors: dict[str, str] = {}
        for start in range(0, len(distinct), _SYMBOL_CHUNK):
            chunk = distinct[start : start + _SYMBOL_CHUNK]
            try:
                resp = await self._http().get(
                    f"/gene/symbol/{','.join(chunk)}/taxon/{tx}/dataset_report"
                )
                resp.raise_for_status()
                for r in _report_payload(resp, "gene").get("reports") or []:
                    gene = r.get("gene")
                    if not gene or gene.get("gene_id") is None:
                        continue
                    echoed_queries = r.get("query")
                    if (
                        not isinstance(echoed_queries, list)
                        or not echoed_queries
                        or any(echo not in chunk for echo in echoed_queries)
                    ):
                        raise _InvalidResponse(
                            "NCBI gene report cannot be correlated to requested symbol"
                        )
                    for echoed in echoed_queries:
                        by_symbol.setdefault(echoed, {})[
                            json.dumps(gene, sort_keys=True, separators=(",", ":"))
                        ] = gene
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    errors.update(dict.fromkeys(chunk, f"NCBI gene error: {format_exc(exc)}"))
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                errors.update(dict.fromkeys(chunk, f"NCBI gene error: {format_exc(exc)}"))

        records: list[LookupRecord] = []
        for q, symbol in zip(queries, symbols):
            if symbol in errors:
                records.append(LookupRecord(query=q, error=errors[symbol]))
                continue
            matches = list(by_symbol.get(symbol, {}).values()) if symbol else []
            if len(matches) > 1:
                candidates = sorted(
                    matches, key=lambda g: (int(g["gene_id"]), json.dumps(g, sort_keys=True))
                )
                records.append(
                    LookupRecord(
                        query=q,
                        error="Ambiguous NCBI gene symbol; review candidates: "
                        + json.dumps(candidates, sort_keys=True),
                    )
                )
                continue
            gene = matches[0] if matches else None
            if gene is None:
                records.append(LookupRecord(query=q, found=False))
                continue
            records.append(
                LookupRecord(
                    query=q,
                    found=True,
                    values={
                        vocab.GENE_ID: int(gene["gene_id"]),
                        vocab.GENE_SYMBOL: gene.get("symbol"),
                        vocab.GENE_NAME: gene.get("description"),
                        vocab.GENE_ORGANISM: gene.get("taxname"),
                    },
                )
            )
        return records

    async def describe_gene(
        self, queries: list[dict[str, Any]], *, groups: frozenset[str]
    ) -> list[LookupRecord]:
        """Gene ids -> summaries (+ products if that group was requested).

        The whole batch is resolved with chunked multi-id ``dataset_report`` requests
        (one per ``_GENE_ID_CHUNK`` genes) instead of one request per gene; product
        reports — a genuinely per-gene endpoint — are then fetched concurrently.
        """
        want_products = "products" in groups
        gids = [str(q.get(vocab.GENE_ID, "") or "").strip() for q in queries]
        distinct = sorted({g for g in gids if g})
        summaries: dict[str, dict[str, Any]] = {}
        source_errors: dict[str, str] = {}
        for start in range(0, len(distinct), _GENE_ID_CHUNK):
            chunk = distinct[start : start + _GENE_ID_CHUNK]
            try:
                summaries.update(await self._gene_reports(chunk))
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    source_errors.update(
                        dict.fromkeys(chunk, f"NCBI report error: {format_exc(exc)}")
                    )
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                source_errors.update(dict.fromkeys(chunk, f"NCBI report error: {format_exc(exc)}"))

        products: dict[str, list[dict[str, Any]]] = {}
        enrichment_errors: dict[str, str] = {}
        if want_products:
            found = [g for g in distinct if g in summaries]
            products, enrichment_errors = await _enrich(
                self._fetch_gene_products, found, limit=self._max_concurrency
            )

        records: list[LookupRecord] = []
        for q, gid in zip(queries, gids):
            if gid in source_errors:
                records.append(LookupRecord(query=q, error=source_errors[gid]))
                continue
            gene = summaries.get(gid) if gid else None
            if gene is None:
                records.append(LookupRecord(query=q, found=False))
                continue
            if gid in enrichment_errors:
                records.append(
                    LookupRecord(query=q, error=f"NCBI products error: {enrichment_errors[gid]}")
                )
                continue
            values = self._gene_summary(gene)
            if want_products and gid in products:
                values[vocab.GENE_PRODUCTS] = products[gid]
                values[vocab.GENE_PRODUCT_COVERAGE] = {
                    "complete": True,
                    "observed_records": len(products[gid]),
                    "returned_records": len(products[gid]),
                    "scope": "product_report_transcripts",
                }
            records.append(LookupRecord(query=q, found=True, values=values))
        return records

    async def _gene_reports(self, gids: list[str]) -> dict[str, dict[str, Any]]:
        """Batch-fetch gene summaries by id, keyed by ``gene_id`` (the gene analogue
        of :meth:`_dataset_report`).

        Hits the multi-id ``gene/id/{ids}/dataset_report`` endpoint with a
        comma-separated id list, chunked to keep the URL bounded and paginated via
        ``next_page_token`` — one request per chunk instead of one per gene.
        """
        out: dict[str, dict[str, Any]] = {}
        for start in range(0, len(gids), _GENE_ID_CHUNK):
            chunk = gids[start : start + _GENE_ID_CHUNK]
            if not chunk:
                continue
            page_token: str | None = None
            guard = _PageGuard(self._max_report_pages)
            while True:
                guard.check(page_token)
                params: dict[str, Any] = {"page_size": _PAGE_LIMIT}
                if page_token:
                    params["page_token"] = page_token
                resp = await self._http().get(
                    f"/gene/id/{','.join(chunk)}/dataset_report", params=params
                )
                guard.check_response(resp)
                body = _report_payload(resp, "gene")
                for r in body.get("reports") or []:
                    gene = r.get("gene")
                    if str(gene["gene_id"]) not in chunk:
                        raise _InvalidResponse("NCBI gene response contains unrequested identifier")
                    out[str(gene["gene_id"])] = gene
                page_token = body.get("next_page_token")
                if not page_token:
                    break
        return out

    async def _fetch_gene_products(self, gid: str) -> list[dict[str, Any]]:
        """Transcript + protein products of a gene (compact rows)."""
        out: list[dict[str, Any]] = []
        token: str | None = None
        guard = _PageGuard(self._max_report_pages)
        while True:
            guard.check(token)
            params: dict[str, Any] = {"page_size": 1000}
            if token:
                params["page_token"] = token
            resp = await self._http().get(f"/gene/id/{gid}/product_report", params=params)
            guard.check_response(resp)
            body = _report_payload(resp, "product")
            for report in body["reports"]:
                product = report.get("product") or {}
                for transcript in product.get("transcripts") or []:
                    protein = transcript.get("protein") or {}
                    out.append(
                        {
                            "transcript": transcript.get("accession_version"),
                            "name": transcript.get("name"),
                            "protein": protein.get("accession_version"),
                            "protein_name": protein.get("name"),
                        }
                    )
            token = body.get("next_page_token")
            if not token:
                return out

    async def list_orthologs(
        self, queries: list[dict[str, Any]], *, taxon_filter: str | None = None
    ) -> list[LookupRecord]:
        """One gene id -> its ortholog gene ids across taxa (excludes the query gene)."""

        async def one(q):
            gid = str(q.get(vocab.GENE_ID, "") or "").strip()
            if not gid:
                return LookupRecord(query=q, found=False)
            try:
                orthologs = await self._fetch_orthologs(gid, taxon_filter)
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    return LookupRecord(query=q, found=False)
                return LookupRecord(query=q, error=f"NCBI orthologs error: {format_exc(exc)}")
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                return LookupRecord(query=q, error=f"NCBI orthologs error: {format_exc(exc)}")
            if not orthologs:
                return LookupRecord(query=q, found=False)
            return LookupRecord(
                query=q,
                found=True,
                values={
                    vocab.GENE_ID: [o["gene_id"] for o in orthologs],
                    vocab.ORTHOLOG_COUNT: len(orthologs),
                    vocab.ORTHOLOG_RECORDS: orthologs[:_CHILDREN_LIMIT],
                },
            )

        return await self._distinct_queries(queries, vocab.GENE_ID, one)

    async def _fetch_orthologs(self, gid: str, taxon_filter: str | None) -> list[dict[str, Any]]:
        """Paginate gene/id/{id}/orthologs, excluding the query gene; distinct + ordered."""
        out: dict[int, dict[str, Any]] = {}
        page_token: str | None = None
        guard = _PageGuard(self._max_report_pages)
        while True:
            guard.check(page_token)
            params: dict[str, Any] = {"page_size": 1000}
            if taxon_filter:
                params["taxon_filter"] = taxon_filter
            if page_token:
                params["page_token"] = page_token
            resp = await self._http().get(f"/gene/id/{gid}/orthologs", params=params)
            guard.check_response(resp)
            body = _report_payload(resp, "gene")
            for r in body.get("reports") or []:
                g = r.get("gene") or {}
                oid = _identifier(g.get("gene_id"))
                if oid is None or str(oid) == gid or oid in out:
                    continue  # skip the query gene itself
                out[oid] = {
                    "gene_id": int(oid),
                    "symbol": g.get("symbol"),
                    "organism": g.get("taxname"),
                }
            page_token = body.get("next_page_token")
            if not page_token:
                break
        return [out[k] for k in sorted(out)]

    # --- HTTP shape parsing ------------------------------------------------

    async def _dataset_report(self, taxons: list[str]) -> dict[str, dict]:
        """Batch resolve taxons to nodes, keyed by the query string that matched."""
        out: dict[str, dict] = {}
        for start in range(0, len(taxons), _PAGE_LIMIT):
            chunk = taxons[start : start + _PAGE_LIMIT]
            if not chunk:
                continue
            resp = await self._http().post("/taxonomy/dataset_report", json={"taxons": chunk})
            resp.raise_for_status()
            payload = _report_payload(resp, "taxonomy")
            # Datasets v2 now returns "reports"; older responses used "taxonomy_nodes".
            for entry in payload.get("reports") or payload.get("taxonomy_nodes") or []:
                node = entry.get("taxonomy")
                echoed = entry.get("query")
                if (
                    not isinstance(echoed, list)
                    or not echoed
                    or any(str(q) not in chunk for q in echoed)
                ):
                    raise _InvalidResponse(
                        "NCBI taxonomy report cannot be correlated to requested input"
                    )
                if node is None:
                    invalid = [
                        identifier
                        for error in entry["errors"]
                        for identifier in error["invalid_identifiers"]
                    ]
                    if any(
                        str(identifier) not in {str(q) for q in echoed} for identifier in invalid
                    ):
                        raise _InvalidResponse(
                            "NCBI taxonomy absence contains unrequested identifiers"
                        )
                    continue
                for q in echoed:
                    out[str(q)] = node
        return out

    async def _fuzzy_match(self, query: str) -> TaxonMatch:
        resp = await self._http().get(
            f"/taxonomy/taxon_suggest/{query}", params={"exact_match": "false"}
        )
        resp.raise_for_status()
        body = _object(resp.json(), "suggestions response")
        # The live suggest endpoint returns {} for zero suggestions (protobuf defaults).
        if body and "sci_name_and_ids" not in body:
            raise _InvalidResponse("NCBI suggestions response lacks sci_name_and_ids")
        suggestions = _objects(body.get("sci_name_and_ids", []), "suggestions")
        for suggestion in suggestions:
            _identifier(suggestion.get("tax_id"))
            for field in ("sci_name", "rank"):
                if suggestion.get(field) is not None and not isinstance(suggestion[field], str):
                    raise _InvalidResponse(f"NCBI suggestion {field} must be a string")
        if not suggestions:
            return TaxonMatch(query=query, status=TaxonMatchStatus.NO_MATCH)
        candidates = [
            CandidateMatch(
                taxid=int(s["tax_id"]),
                name=s.get("sci_name", ""),
                rank=s.get("rank", "") or "",
                match_type="fuzzy",
                score=_rescore(query, s.get("sci_name")),
            )
            for s in suggestions
            if s.get("tax_id")
        ]
        # Ranking is source-local. Taxon identity, name and rank form a total
        # tie-break; duplicate suggestions must not create false ambiguity.
        candidates.sort(
            key=lambda candidate: (
                -(candidate.score or 0.0),
                candidate.taxid,
                candidate.name,
                candidate.rank,
            )
        )
        distinct_candidates: dict[int, CandidateMatch] = {}
        for candidate in candidates:
            distinct_candidates.setdefault(candidate.taxid, candidate)
        candidates = list(distinct_candidates.values())
        if not candidates:
            return TaxonMatch(query=query, status=TaxonMatchStatus.NO_MATCH)
        if len(candidates) == 1:
            top = candidates[0]
            return TaxonMatch(
                query=query,
                status=TaxonMatchStatus.FUZZY_UNIQUE,
                taxid=top.taxid,
                scientific_name=top.name,
                rank=top.rank,
                match_type="fuzzy",
                score=top.score,
                requires_review=True,
                candidates=candidates,
            )
        return TaxonMatch(
            query=query,
            status=TaxonMatchStatus.AMBIGUOUS,
            match_type="fuzzy",
            requires_review=True,
            candidates=candidates,
        )

    async def _attach_lineage(self, matches: dict[str, TaxonMatch]) -> None:
        """Resolve ancestor taxids (deduped across the batch) to name/rank entries."""
        ancestor_ids: set[int] = set()
        for m in matches.values():
            ancestor_ids.update(m.lineage_taxids)
        if not ancestor_ids:
            return
        nodes: dict[str, dict] = {}
        failed_ancestors: dict[int, str] = {}
        identifiers = [str(t) for t in sorted(ancestor_ids)]
        for start in range(0, len(identifiers), _PAGE_LIMIT):
            chunk = identifiers[start : start + _PAGE_LIMIT]
            try:
                nodes.update(await self._dataset_report(chunk))
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                failed_ancestors.update(dict.fromkeys((int(t) for t in chunk), format_exc(exc)))
        by_taxid: dict[int, dict] = {}
        for node in nodes.values():
            tid = node.get("tax_id")
            if tid is not None:
                by_taxid[int(tid)] = node
        for m in matches.values():
            if not m.lineage_taxids or m.taxid is None:
                continue
            failed = next(
                (failed_ancestors[tid] for tid in m.lineage_taxids if tid in failed_ancestors), None
            )
            if failed is not None:
                m.status = TaxonMatchStatus.ERROR
                m.error = f"NCBI lineage error: {failed}"
                continue
            entries = [
                LineageEntry(
                    taxid=tid,
                    rank=(_node_rank(by_taxid.get(tid, {})) or ""),
                    name=(_node_name(by_taxid.get(tid, {})) or ""),
                )
                for tid in m.lineage_taxids
            ]
            entries.append(
                LineageEntry(taxid=m.taxid, rank=m.rank or "", name=m.scientific_name or "")
            )
            m.lineage = entries

    def _node_match(self, query: str, node: dict[str, Any], *, match_type: str) -> TaxonMatch:
        taxid = int(node["tax_id"]) if node.get("tax_id") is not None else None
        name = _node_name(node)
        lineage_taxids = _node_parents(node)
        parent = lineage_taxids[-1] if lineage_taxids else None
        match = TaxonMatch(
            query=query,
            status=TaxonMatchStatus.RESOLVED,
            taxid=taxid,
            scientific_name=name,
            rank=_node_rank(node),
            parent_taxid=parent,
            match_type=match_type,
            score=None if match_type == "exact" else _rescore(query, name),
        )
        match.lineage_taxids = lineage_taxids
        return match
