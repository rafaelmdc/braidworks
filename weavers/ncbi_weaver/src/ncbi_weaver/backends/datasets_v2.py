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

import logging
from typing import Any

import httpx
from rapidfuzz import fuzz

from braidworks.core import LookupRecord, format_exc, is_not_found_status

from ..intermediate import CandidateMatch, LineageEntry, TaxonMatch, TaxonMatchStatus
from .. import vocab

_CHILDREN_LIMIT = 200  # top-N children surfaced in records (ids/count stay the true total)

logger = logging.getLogger("ncbi_weaver.api")

DEFAULT_BASE_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2"
_PAGE_LIMIT = 1000


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


def _rescore(query: str, name: str | None) -> float:
    """RapidFuzz token-set ratio on the 0..100 scale, matching the local fuzzy scale."""
    if not name:
        return 0.0
    return float(fuzz.token_set_ratio(query.lower(), name.lower()))


class DatasetsV2Backend:
    """Resolution backend backed by the NCBI Datasets v2 REST API."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        allow_fuzzy: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = client
        self._owns_client = client is None
        self._allow_fuzzy = allow_fuzzy

    def is_configured(self) -> bool:
        """The API backend is always usable; it needs no local data."""
        return True

    def fingerprint(self) -> str:
        """Datasets v2 is a live service, so the fingerprint is a fixed identifier."""
        return "datasets-v2"

    def _http(self) -> httpx.AsyncClient:
        """Return the HTTP client, lazily creating one if none was injected."""
        if self._client is None:
            headers = {"api-key": self._api_key} if self._api_key else {}
            self._client = httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=30.0)
        return self._client

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
        nodes = await self._dataset_report(queries)

        matches: dict[str, TaxonMatch] = {}
        misses: list[str] = []
        for q in queries:
            node = nodes.get(q)
            if node is not None:
                matches[q] = self._node_match(q, node, match_type="exact")
            elif capability_id == vocab.RESOLVE_NAME and self._allow_fuzzy:
                misses.append(q)
            else:
                matches[q] = TaxonMatch(query=q, status=TaxonMatchStatus.NO_MATCH)

        for q in misses:
            matches[q] = await self._fuzzy_match(q)

        if need_lineage:
            await self._attach_lineage(matches)

        # Preserve input order (queries may contain duplicates → reuse the match).
        return [matches[q] for q in queries]

    async def list_children(
        self, queries: list[dict[str, Any]], *, rank: str
    ) -> list[LookupRecord]:
        """One taxid -> its descendant taxids of ``rank`` (walks the subtree)."""
        rank_norm = (rank or "species").strip().lower()
        records: list[LookupRecord] = []
        for q in queries:
            taxid = str(q.get(vocab.TAXON_ID, "") or "").strip()
            if not taxid:
                records.append(LookupRecord(query=q, found=False))
                continue
            try:
                children = await self._fetch_children(taxid, rank_norm)
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    records.append(LookupRecord(query=q, found=False))
                    continue
                logger.warning("NCBI children failed for %r: %s", taxid, exc)
                records.append(LookupRecord(query=q, error=f"NCBI children error: {format_exc(exc)}"))
                continue
            except httpx.HTTPError as exc:
                logger.warning("NCBI children failed for %r: %s", taxid, exc)
                records.append(LookupRecord(query=q, error=f"NCBI children error: {format_exc(exc)}"))
                continue
            if not children:
                records.append(LookupRecord(query=q, found=False))
                continue
            ids = [c["taxid"] for c in children]
            records.append(LookupRecord(query=q, found=True, values={
                # The fan dimension: every distinct descendant taxid (uncapped).
                vocab.TAXON_ID: ids,
                vocab.CHILDREN_COUNT: len(ids),
                vocab.CHILDREN_RECORDS: children[:_CHILDREN_LIMIT],
            }))
        return records

    async def _fetch_children(self, taxid: str, rank: str) -> list[dict[str, Any]]:
        """Walk dataset_report?children=true, keep distinct descendants of ``rank``."""
        out: dict[int, dict[str, Any]] = {}
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"children": "true", "page_size": 1000}
            if page_token:
                params["page_token"] = page_token
            resp = await self._http().get(
                f"/taxonomy/taxon/{taxid}/dataset_report", params=params
            )
            resp.raise_for_status()
            body = resp.json()
            for entry in body.get("reports") or []:
                node = entry.get("taxonomy") or {}
                tid = node.get("tax_id")
                if tid is None or str(tid) == taxid:
                    continue  # skip the queried node itself
                if rank and (node.get("rank") or "").lower() != rank:
                    continue
                if tid not in out:
                    out[tid] = {"taxid": tid, "name": _node_name(node),
                                "rank": (node.get("rank") or "").lower()}
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
        records: list[LookupRecord] = []
        for q in queries:
            taxid = str(q.get(vocab.TAXON_ID, "") or "").strip()
            if not taxid:
                records.append(LookupRecord(query=q, found=False))
                continue
            try:
                assemblies = await self._fetch_genomes(taxid, params)
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    records.append(LookupRecord(query=q, found=False))
                    continue
                records.append(LookupRecord(query=q, error=f"NCBI genomes error: {format_exc(exc)}"))
                continue
            except httpx.HTTPError as exc:
                records.append(LookupRecord(query=q, error=f"NCBI genomes error: {format_exc(exc)}"))
                continue
            if not assemblies:
                records.append(LookupRecord(query=q, found=False))
                continue
            records.append(LookupRecord(query=q, found=True, values={
                vocab.GENOME_ACCESSION: [a["accession"] for a in assemblies],  # the fan dimension
                vocab.ASSEMBLY_COUNT: len(assemblies),
                vocab.ASSEMBLY_RECORDS: assemblies[:_CHILDREN_LIMIT],
            }))
        return records

    async def _fetch_genomes(self, taxid: str, base_params: dict) -> list[dict[str, Any]]:
        """Paginate genome/taxon/{taxid}/dataset_report into compact assembly rows."""
        out: dict[str, dict[str, Any]] = {}
        page_token: str | None = None
        while True:
            params = dict(base_params)
            if page_token:
                params["page_token"] = page_token
            resp = await self._http().get(
                f"/genome/taxon/{taxid}/dataset_report", params=params
            )
            resp.raise_for_status()
            body = resp.json()
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
        """One genome accession -> assembly detail (+ sequences if that group was asked)."""
        want_sequences = "sequences" in groups
        records: list[LookupRecord] = []
        for q in queries:
            acc = str(q.get(vocab.GENOME_ACCESSION, "") or "").strip()
            if not acc:
                records.append(LookupRecord(query=q, found=False))
                continue
            try:
                values = await self._describe_one_genome(acc, want_sequences)
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    records.append(LookupRecord(query=q, found=False))
                    continue
                records.append(LookupRecord(query=q, error=f"NCBI genome error: {format_exc(exc)}"))
                continue
            except httpx.HTTPError as exc:
                records.append(LookupRecord(query=q, error=f"NCBI genome error: {format_exc(exc)}"))
                continue
            if values is None:
                records.append(LookupRecord(query=q, found=False))
                continue
            records.append(LookupRecord(query=q, found=True, values=values))
        return records

    async def _describe_one_genome(
        self, acc: str, want_sequences: bool
    ) -> dict[str, Any] | None:
        resp = await self._http().get(f"/genome/accession/{acc}/dataset_report")
        resp.raise_for_status()
        reports = resp.json().get("reports") or []
        if not reports:
            return None
        a = reports[0]
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
        if want_sequences:
            values[vocab.SEQUENCE_RECORDS] = await self._fetch_sequences(acc)
        return values

    async def _fetch_sequences(self, acc: str) -> list[dict[str, Any]]:
        """Per-sequence reports for an assembly (chromosomes/plasmids/contigs)."""
        out: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 1000}
            if page_token:
                params["page_token"] = page_token
            resp = await self._http().get(
                f"/genome/accession/{acc}/sequence_reports", params=params
            )
            resp.raise_for_status()
            body = resp.json()
            for s in body.get("reports") or []:
                out.append({
                    "name": s.get("chr_name") or s.get("sequence_name"),
                    "role": s.get("role"),
                    "length": s.get("length"),
                    "refseq_accession": s.get("refseq_accession"),
                    "genbank_accession": s.get("genbank_accession"),
                })
            page_token = body.get("next_page_token")
            if not page_token:
                break
        return out[:_CHILDREN_LIMIT]

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
        """A gene symbol (in ``taxon``) -> its NCBI gene id + summary."""
        tx = (taxon or "9606").strip()
        records: list[LookupRecord] = []
        for q in queries:
            symbol = str(q.get(vocab.PROTEIN_QUERY, "") or "").strip()
            if not symbol:
                records.append(LookupRecord(query=q, found=False))
                continue
            try:
                resp = await self._http().get(
                    f"/gene/symbol/{symbol}/taxon/{tx}/dataset_report"
                )
                resp.raise_for_status()
                reports = resp.json().get("reports") or []
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    records.append(LookupRecord(query=q, found=False))
                    continue
                records.append(LookupRecord(query=q, error=f"NCBI gene error: {format_exc(exc)}"))
                continue
            except httpx.HTTPError as exc:
                records.append(LookupRecord(query=q, error=f"NCBI gene error: {format_exc(exc)}"))
                continue
            gene = next((r.get("gene") for r in reports if r.get("gene")), None)
            if not gene or gene.get("gene_id") is None:
                records.append(LookupRecord(query=q, found=False))
                continue
            records.append(LookupRecord(query=q, found=True, values={
                vocab.GENE_ID: int(gene["gene_id"]),
                vocab.GENE_SYMBOL: gene.get("symbol"),
                vocab.GENE_NAME: gene.get("description"),
                vocab.GENE_ORGANISM: gene.get("taxname"),
            }))
        return records

    async def describe_gene(
        self, queries: list[dict[str, Any]], *, groups: frozenset[str]
    ) -> list[LookupRecord]:
        """One gene id -> summary (+ products if that group was requested)."""
        want_products = "products" in groups
        records: list[LookupRecord] = []
        for q in queries:
            gid = str(q.get(vocab.GENE_ID, "") or "").strip()
            if not gid:
                records.append(LookupRecord(query=q, found=False))
                continue
            try:
                resp = await self._http().get(f"/gene/id/{gid}/dataset_report")
                resp.raise_for_status()
                reports = resp.json().get("reports") or []
                gene = next((r.get("gene") for r in reports if r.get("gene")), None)
                if gene is None:
                    records.append(LookupRecord(query=q, found=False))
                    continue
                values = self._gene_summary(gene)
                if want_products:
                    values[vocab.GENE_PRODUCTS] = await self._fetch_gene_products(gid)
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    records.append(LookupRecord(query=q, found=False))
                    continue
                records.append(LookupRecord(query=q, error=f"NCBI gene error: {format_exc(exc)}"))
                continue
            except httpx.HTTPError as exc:
                records.append(LookupRecord(query=q, error=f"NCBI gene error: {format_exc(exc)}"))
                continue
            records.append(LookupRecord(query=q, found=True, values=values))
        return records

    async def _fetch_gene_products(self, gid: str) -> list[dict[str, Any]]:
        """Transcript + protein products of a gene (compact rows)."""
        resp = await self._http().get(f"/gene/id/{gid}/product_report", params={"page_size": 1000})
        resp.raise_for_status()
        out: list[dict[str, Any]] = []
        for r in resp.json().get("reports") or []:
            product = r.get("product") or {}
            for t in product.get("transcripts") or []:
                prot = t.get("protein") or {}
                out.append({
                    "transcript": t.get("accession_version"),
                    "name": t.get("name"),
                    "protein": prot.get("accession_version"),
                    "protein_name": prot.get("name"),
                })
        return out[:_CHILDREN_LIMIT]

    async def list_orthologs(
        self, queries: list[dict[str, Any]], *, taxon_filter: str | None = None
    ) -> list[LookupRecord]:
        """One gene id -> its ortholog gene ids across taxa (excludes the query gene)."""
        records: list[LookupRecord] = []
        for q in queries:
            gid = str(q.get(vocab.GENE_ID, "") or "").strip()
            if not gid:
                records.append(LookupRecord(query=q, found=False))
                continue
            try:
                orthologs = await self._fetch_orthologs(gid, taxon_filter)
            except httpx.HTTPStatusError as exc:
                if is_not_found_status(exc.response.status_code):
                    records.append(LookupRecord(query=q, found=False))
                    continue
                records.append(LookupRecord(query=q, error=f"NCBI orthologs error: {format_exc(exc)}"))
                continue
            except httpx.HTTPError as exc:
                records.append(LookupRecord(query=q, error=f"NCBI orthologs error: {format_exc(exc)}"))
                continue
            if not orthologs:
                records.append(LookupRecord(query=q, found=False))
                continue
            records.append(LookupRecord(query=q, found=True, values={
                vocab.GENE_ID: [o["gene_id"] for o in orthologs],  # the fan dimension
                vocab.ORTHOLOG_COUNT: len(orthologs),
                vocab.ORTHOLOG_RECORDS: orthologs[:_CHILDREN_LIMIT],
            }))
        return records

    async def _fetch_orthologs(
        self, gid: str, taxon_filter: str | None
    ) -> list[dict[str, Any]]:
        """Paginate gene/id/{id}/orthologs, excluding the query gene; distinct + ordered."""
        out: dict[int, dict[str, Any]] = {}
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 1000}
            if taxon_filter:
                params["taxon_filter"] = taxon_filter
            if page_token:
                params["page_token"] = page_token
            resp = await self._http().get(f"/gene/id/{gid}/orthologs", params=params)
            resp.raise_for_status()
            body = resp.json()
            for r in body.get("reports") or []:
                g = r.get("gene") or {}
                oid = g.get("gene_id")
                if oid is None or str(oid) == gid or oid in out:
                    continue  # skip the query gene itself
                out[oid] = {"gene_id": int(oid), "symbol": g.get("symbol"),
                            "organism": g.get("taxname")}
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
            payload = resp.json()
            # Datasets v2 now returns "reports"; older responses used "taxonomy_nodes".
            for entry in payload.get("reports") or payload.get("taxonomy_nodes") or []:
                node = entry.get("taxonomy")
                if not node:
                    continue
                for q in entry.get("query", []):
                    out[str(q)] = node
        return out

    async def _fuzzy_match(self, query: str) -> TaxonMatch:
        resp = await self._http().get(
            f"/taxonomy/taxon_suggest/{query}", params={"exact_match": "false"}
        )
        resp.raise_for_status()
        suggestions = resp.json().get("sci_name_and_ids", []) or []
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
        nodes = await self._dataset_report([str(t) for t in sorted(ancestor_ids)])
        by_taxid: dict[int, dict] = {}
        for node in nodes.values():
            tid = node.get("tax_id")
            if tid is not None:
                by_taxid[int(tid)] = node
        for m in matches.values():
            if not m.lineage_taxids or m.taxid is None:
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
