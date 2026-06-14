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

from braidworks.core import BackendBase, LookupRecord, is_not_found_status

logger = logging.getLogger("string_weaver.api")

DEFAULT_BASE_URL = "https://string-db.org/api"
DEFAULT_LIMIT = 25  # max partners per protein (most confident first)
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
        # One interaction_partners call per accession; the whole edge list arrives at
        # once, so we compute every leaf and let the shared mapper filter.
        records: list[LookupRecord] = []
        for query in queries:
            accession = str(query.get("protein.uniprot.accession", "")).strip()
            records.append(await self._resolve_one(query, accession))
        return records

    async def _resolve_one(self, query: dict[str, Any], accession: str) -> LookupRecord:
        if not accession:
            return LookupRecord(query=query, found=False)
        try:
            resp = await self._http().get(
                "/json/interaction_partners",
                params={
                    "identifiers": accession,
                    "limit": str(self._limit),
                    "caller_identity": "braidworks",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            # STRING returns 400/404 for an identifier it can't map — that's a normal
            # data outcome (NO_MATCH), not a system error.
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("STRING lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"STRING API error: {exc}")
        except httpx.HTTPError as exc:  # network/timeout problem is a per-entity error
            logger.warning("STRING lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"STRING API error: {exc}")

        if not isinstance(payload, list) or not payload:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_extract(payload))
