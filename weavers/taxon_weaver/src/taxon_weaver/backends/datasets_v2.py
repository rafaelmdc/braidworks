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

from ..intermediate import CandidateMatch, LineageEntry, TaxonMatch, TaxonMatchStatus
from .. import vocab

logger = logging.getLogger("taxon_weaver.api")

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
