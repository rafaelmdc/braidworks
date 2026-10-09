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
partner name ascending — within the upstream retrieval limit. This is a bounded observation, not
a complete interaction network.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (interaction_partners for P04637 -> TP53's partners).
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

logger = logging.getLogger("string_weaver.api")

DEFAULT_BASE_URL = "https://version-12-5.string-db.org/api"
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


class _InvalidResponse(ValueError):
    """An invalid or uncorrelatable STRING source response."""


def _validate_rows(body: Any, path: str, identifiers: list[str]) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise _InvalidResponse("STRING response must be a list")
    for row in body:
        if not isinstance(row, dict):
            raise _InvalidResponse("STRING row must be an object")
        if path.endswith("get_string_ids"):
            if (
                row.get("queryItem") not in identifiers
                or not isinstance(row.get("stringId"), str)
                or not row["stringId"]
            ):
                raise _InvalidResponse(
                    "STRING mapping cannot be correlated to requested identifier"
                )
        else:
            if row.get("stringId_A") not in identifiers:
                raise _InvalidResponse("STRING edge cannot be correlated to requested identifier")
            for field in ("stringId_B", "preferredName_B"):
                if not isinstance(row.get(field), str) or not row[field]:
                    raise _InvalidResponse(f"STRING edge must contain {field}")
            for field in ("score", *_CHANNELS):
                value = row.get(field)
                if value is not None and (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise _InvalidResponse(f"STRING {field} must be a finite number or null")
        id_fields = (
            ("stringId",) if path.endswith("get_string_ids") else ("stringId_A", "stringId_B")
        )
        taxa = []
        for field in id_fields:
            taxon, separator, protein = row[field].partition(".")
            if not separator or not taxon.isdigit() or int(taxon) < 1 or not protein:
                raise _InvalidResponse("STRING identifier must preserve taxon and protein identity")
            taxa.append(int(taxon))
        if len(set(taxa)) != 1 or (
            row.get("ncbiTaxonId") is not None and str(row["ncbiTaxonId"]) != str(taxa[0])
        ):
            raise _InvalidResponse("STRING identity conflicts with reported taxon")
    return body


def _edge(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "partner": raw["preferredName_B"],
        "string_id": raw["stringId_B"],
        "source_id": raw["stringId_A"],
        "taxon_id": int(raw["stringId_B"].split(".", 1)[0]),
        "score": raw.get("score"),
        "channels": {label: raw[key] for key, label in _CHANNELS.items() if raw.get(key)},
    }


def _extract(payload: list[dict[str, Any]]) -> dict[str, Any]:
    # Collapse logical source/target edges; keep all distinct observed evidence.
    by_edge: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for raw in payload:
        by_edge.setdefault((raw["stringId_A"], raw["stringId_B"]), {})[
            json.dumps(raw, sort_keys=True)
        ] = raw
    records = []
    for evidence in by_edge.values():
        observed = sorted(
            evidence.values(),
            key=lambda row: (
                -(row.get("score") or 0.0),
                json.dumps(row, sort_keys=True),
            ),
        )
        record = _edge(observed[0])
        record["evidence"] = observed
        records.append(record)
    records.sort(key=lambda row: (-(row["score"] or 0.0), row["string_id"], row["source_id"]))
    return {
        "string.id": list(dict.fromkeys(row["string_id"] for row in records)),
        "protein.interaction.partners": [row["partner"] for row in records],
        "protein.interaction.count": len(records),
        "protein.interaction.records": records,
    }


class StringApiBackend(HTTPClientLifecycle, BackendBase):
    """STRING REST backend. Always configured — the API is free, no key."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self._configure_client(client, base_url)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        self._limit = limit

    def is_configured(self) -> bool:
        """STRING REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """Identify the effective endpoint and result-affecting policy, not live contents."""
        endpoint = (
            str(self._client.base_url)
            if self._client is not None and str(self._client.base_url)
            else self._base_url
        )
        return remote_fingerprint(
            "string-api",
            endpoint,
            limit=self._limit,
            release="12.5" if endpoint.rstrip("/") == DEFAULT_BASE_URL else "custom-or-unversioned",
        )

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return PacedHTTPClient(self._client, "string")

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
        idmap, mapping_errors = await self._string_ids(distinct)
        partners, partner_errors = await self._partners(sorted(set(idmap.values())))

        records: list[LookupRecord] = []
        for query, acc in zip(queries, accs):
            string_id = idmap.get(acc) if acc else None
            edges = partners.get(string_id) if string_id else None
            error = mapping_errors.get(acc) or partner_errors.get(string_id)
            if error:
                records.append(LookupRecord(query=query, error=error))
            elif not edges:
                records.append(
                    LookupRecord(
                        query=query,
                        found=False,
                        warnings=(
                            (
                                f"No edges observed within STRING retrieval limit={self._limit}; "
                                "network completeness is not established."
                            ),
                        )
                        if string_id
                        else (),
                    )
                )
            else:
                values = _extract(edges)
                values["protein.interaction.coverage"] = {
                    "scope": "retrieved_interaction_partners",
                    "request_limit": self._limit,
                    "observed_edges": values["protein.interaction.count"],
                    "observed_partners": len(values["string.id"]),
                    "complete": None,
                    "count_scope": "observed_edges",
                    "fan_scope": "retrieved_partners",
                }
                records.append(
                    LookupRecord(
                        query=query,
                        found=True,
                        values=values,
                        warnings=(
                            (
                                f"STRING retrieval is bounded by limit={self._limit}; "
                                "counts and fan-out describe retrieved partners, "
                                "not a proven complete network."
                            ),
                        ),
                    )
                )
        return records

    async def _string_ids(self, accessions: list[str]) -> tuple[dict[str, str], dict[str, str]]:
        """Bulk-resolve accessions to STRING ids, keyed by the echoed ``queryItem``."""
        out: dict[str, str] = {}
        errors: dict[str, str] = {}
        for start in range(0, len(accessions), _ID_CHUNK):
            chunk = accessions[start : start + _ID_CHUNK]
            if not chunk:
                continue
            try:
                rows = await self._get("/json/get_string_ids", "\r".join(chunk))
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                errors.update(dict.fromkeys(chunk, f"STRING API error: {format_exc(exc)}"))
                continue
            matches: dict[str, set[str]] = {}
            for row in rows:
                matches.setdefault(row["queryItem"], set()).add(row["stringId"])
            for query, identities in matches.items():
                if len(identities) != 1:
                    errors[query] = "Ambiguous STRING identity: " + json.dumps(sorted(identities))
                else:
                    out[query] = next(iter(identities))
        return out, errors

    async def _partners(
        self, string_ids: list[str]
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
        """Bulk-fetch interaction partners, grouped by the query protein (``stringId_A``)."""
        out: dict[str, list[dict[str, Any]]] = {}
        errors: dict[str, str] = {}
        for start in range(0, len(string_ids), _ID_CHUNK):
            chunk = string_ids[start : start + _ID_CHUNK]
            if not chunk:
                continue
            try:
                rows = await self._get(
                    "/json/interaction_partners", "\r".join(chunk), limit=str(self._limit)
                )
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                errors.update(dict.fromkeys(chunk, f"STRING API error: {format_exc(exc)}"))
                continue
            for row in rows:
                out.setdefault(row["stringId_A"], []).append(row)
        return out, errors

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
        return _validate_rows(payload, path, identifiers.split("\r"))
