"""The api backend for string_weaver — the keyless STRING REST API.

Strategy: a UniProt ``protein.uniprot.accession`` is sent to
``GET /json/interaction_partners`` (STRING resolves the accession to its protein +
species itself, so no species input is needed). The returned edges are normalized
into interaction leaves:
  * ``protein.interaction.partners`` — partner display names,
  * ``protein.interaction.count`` — how many,
  * ``protein.interaction.records`` — full edges (partner, combined score, per-channel
    subscores).

**Determinism:** STRING returns partners ranked by confidence, but ties are not
ordered stably, so we impose a fixed total order — combined score descending, then
partner name ascending — and cap at ``limit``. So the same accession always yields the
same partner list.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (interaction_partners for P04637 -> TP53's partners).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status

logger = logging.getLogger("string_weaver.api")

DEFAULT_BASE_URL = "https://string-db.org/api"
DEFAULT_LIMIT = 25  # max partners per protein (most confident first)
_ID_CHUNK = 100  # identifiers per STRING request (newline-separated; keeps the URL bounded)
# STRING evidence channels: JSON subscore key -> readable name.
_CHANNELS = {
    "nscore": "neighborhood",
    "fscore": "fusion",
    "pscore": "cooccurrence",
    "ascore": "coexpression",
    "escore": "experimental",
    "dscore": "database",
    "tscore": "textmining",
}


def _edge(raw: dict[str, Any]) -> dict[str, Any] | None:
    """One STRING edge -> a compact record, or None if it has no partner name."""
    partner = raw.get("preferredName_B")
    if not partner:
        return None
    channels = {name: raw.get(key) for key, name in _CHANNELS.items() if raw.get(key)}
    return {
        "partner": partner,
        "string_id": raw.get("stringId_B"),
        "score": raw.get("score"),
        "channels": channels,
    }


def _extract(payload: list[dict[str, Any]]) -> dict[str, Any]:
    """Map STRING's edge list to produced type_ids, in a deterministic order."""
    rows = [e for e in (_edge(r) for r in payload) if e is not None]
    rows.sort(key=lambda r: (-(r["score"] or 0.0), r["partner"]))
    # The fan dimension (set_outputs): each partner's name as a protein.query, so a caller
    # can fan out one child per partner. uniprot.resolve_protein consumes protein.query, so
    # "protein -> all interaction partners -> each resolved protein" chains end-to-end.
    # De-duped, order preserved (best-first).
    queries: list[str] = []
    seen: set[str] = set()
    for r in rows:
        if r["partner"] not in seen:
            seen.add(r["partner"])
            queries.append(r["partner"])
    return {
        "protein.query": queries,
        "protein.interaction.partners": [r["partner"] for r in rows],
        "protein.interaction.count": len(rows),
        "protein.interaction.records": rows,
    }


class StringApiBackend(BackendBase):
    """STRING REST backend. Always configured — the API is free, no key."""

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
        """STRING REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the REST API/release version."""
        return "string-db-v12"

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
        # The whole batch is resolved with two bulk calls — get_string_ids (accessions
        # -> STRING ids) then interaction_partners over the resolved ids — instead of one
        # interaction_partners call per accession. STRING resolves each identifier's
        # species on its own, so a single mixed-species batch is safe; partner edges are
        # grouped back to each query by their ``stringId_A``.
        accs = [str(q.get("protein.uniprot.accession", "")).strip() for q in queries]
        distinct = sorted({a for a in accs if a})
        if not distinct:
            return [LookupRecord(query=q, found=False) for q in queries]
        try:
            idmap = await self._string_ids(distinct)
            partners = await self._partners(sorted(set(idmap.values())))
        except httpx.HTTPError as exc:  # network/server problem is a whole-batch error
            logger.warning("STRING lookup failed: %s", exc)
            err = f"STRING API error: {format_exc(exc)}"
            return [LookupRecord(query=q, error=err) for q in queries]

        records: list[LookupRecord] = []
        for query, acc in zip(queries, accs):
            string_id = idmap.get(acc) if acc else None
            edges = partners.get(string_id) if string_id else None
            if not edges:
                records.append(LookupRecord(query=query, found=False))
            else:
                records.append(LookupRecord(query=query, found=True, values=_extract(edges)))
        return records

    async def _string_ids(self, accessions: list[str]) -> dict[str, str]:
        """Bulk-resolve accessions to STRING ids, keyed by the echoed ``queryItem``."""
        out: dict[str, str] = {}
        for start in range(0, len(accessions), _ID_CHUNK):
            chunk = accessions[start : start + _ID_CHUNK]
            if not chunk:
                continue
            for row in await self._get("/json/get_string_ids", "\r".join(chunk)):
                query_item, string_id = row.get("queryItem"), row.get("stringId")
                if query_item and string_id:
                    out.setdefault(str(query_item), str(string_id))
        return out

    async def _partners(self, string_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        """Bulk-fetch interaction partners, grouped by the query protein (``stringId_A``)."""
        out: dict[str, list[dict[str, Any]]] = {}
        for start in range(0, len(string_ids), _ID_CHUNK):
            chunk = string_ids[start : start + _ID_CHUNK]
            if not chunk:
                continue
            rows = await self._get(
                "/json/interaction_partners", "\r".join(chunk), limit=str(self._limit)
            )
            for row in rows:
                a = row.get("stringId_A")
                if a:
                    out.setdefault(str(a), []).append(row)
        return out

    async def _get(self, path: str, identifiers: str, **extra: str) -> list[dict[str, Any]]:
        """A STRING GET returning the JSON list, mapping the no-match status (400/404)
        to an empty result so a fully-unmappable batch is a clean miss, not an error."""
        params = {"identifiers": identifiers, "caller_identity": "braidworks", **extra}
        resp = await self._http().get(path, params=params)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if is_not_found_status(exc.response.status_code):
                return []
            raise
        payload = resp.json()
        return payload if isinstance(payload, list) else []
