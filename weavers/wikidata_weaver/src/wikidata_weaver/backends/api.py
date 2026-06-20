"""The api backend for wikidata_weaver — the Wikidata Query Service (SPARQL).

Resolves a taxon scientific name (P225) to its Wikidata item (QID), its English
Wikipedia article title (enwiki sitelink), and its English vernacular names (P1843).
The whole input batch is resolved in ONE SPARQL query (VALUES ?sname …) and mapped
back to inputs by the echoed name — never one request per name.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``).

Guide: weaverkit/docs/implementing-backends.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

import httpx

from braidworks.core import (
    BackendBase,
    Candidate,
    MatchStatus,
    ResolverRecord,
    is_not_found_status,
)

# The Wikidata Query Service SPARQL endpoint (distinct from the www. content host).
BASE_URL = "https://query.wikidata.org"
_USER_AGENT = "Cladewright/0.1 (https://github.com/rafaelmdc; rafaelmdcorreia@gmail.com)"

# Resolve P225 (taxon name) -> item, optional enwiki sitelink, optional English P1843.
# ?sname is echoed so we can align rows back to the input batch.
_SPARQL = """
SELECT ?sname ?item ?article ?vn WHERE {{
  VALUES ?sname {{ {values} }}
  ?item wdt:P225 ?sname .
  OPTIONAL {{ ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }}
  OPTIONAL {{ ?item wdt:P1843 ?vn . FILTER(LANG(?vn) = "en") }}
}}
"""


def _qid(item_uri: str) -> str:
    return item_uri.rsplit("/", 1)[-1]


def _title(article_uri: str) -> str:
    # https://en.wikipedia.org/wiki/Brown_bear -> "Brown_bear" (pageviews-ready form)
    return unquote(article_uri.rsplit("/wiki/", 1)[-1])


def _sparql_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class WikidataApiBackend(BackendBase):
    """api backend — calls the keyless Wikidata Query Service."""

    name = "api"

    def __init__(
        self, *, base_url: str = BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._configured = True  # keyless service — always usable

    def is_configured(self) -> bool:
        return self._configured or self._client is not None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=60.0)
        return self._client

    def fingerprint(self) -> str:
        # Wikidata is continuously edited; bucket the cache by query month so results
        # refresh monthly (matches the spec's "query-month" source of truth).
        return "wikidata-api-" + datetime.now(timezone.utc).strftime("%Y-%m")

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[ResolverRecord]:
        names = [str(q.get("organism.scientific_name", "")).strip() for q in queries]

        # Distinct, non-empty names for the VALUES clause (dedup the wire request).
        distinct = sorted({n for n in names if n})
        rows_by_name: dict[str, dict[str, dict[str, Any]]] = {n: {} for n in distinct}
        error: str | None = None

        if distinct:
            query = _SPARQL.format(values=" ".join(_sparql_literal(n) for n in distinct))
            try:
                resp = await self._http().get(
                    "/sparql",
                    params={"query": query, "format": "json"},
                    headers={
                        "Accept": "application/sparql-results+json",
                        "User-Agent": _USER_AGENT,
                    },
                )
                resp.raise_for_status()
                _accumulate(resp.json(), rows_by_name)
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    error = f"Wikidata query failed: HTTP {exc.response.status_code}"
            except httpx.HTTPError as exc:
                error = f"Wikidata query failed: {exc}"

        records: list[ResolverRecord] = []
        for name, query in zip(names, queries):
            if error is not None:
                records.append(
                    ResolverRecord(query=query, status=MatchStatus.ERROR, values={},
                                   candidates=[], error=error)
                )
                continue
            items = rows_by_name.get(name, {})
            if not items:
                records.append(
                    ResolverRecord(query=query, status=MatchStatus.NO_MATCH, values={},
                                   candidates=[])
                )
            elif len(items) == 1:
                ((qid, fields),) = items.items()
                records.append(
                    ResolverRecord(query=query, status=MatchStatus.RESOLVED,
                                   values=_values(qid, fields), candidates=[])
                )
            else:
                # Same scientific name on several items (homonym across nomenclature
                # codes, or duplicate items) — return all for review, deterministically.
                candidates = [
                    Candidate(values=_values(qid, fields))
                    for qid, fields in sorted(items.items())
                ]
                records.append(
                    ResolverRecord(query=query, status=MatchStatus.AMBIGUOUS, values={},
                                   candidates=candidates)
                )
        return records


def _accumulate(
    payload: dict[str, Any], rows_by_name: dict[str, dict[str, dict[str, Any]]]
) -> None:
    """Fold SPARQL bindings into name -> qid -> {title, vernaculars}."""
    for binding in payload.get("results", {}).get("bindings", []):
        sname = binding.get("sname", {}).get("value")
        item = binding.get("item", {}).get("value")
        if not sname or not item or sname not in rows_by_name:
            continue
        qid = _qid(item)
        fields = rows_by_name[sname].setdefault(qid, {"title": None, "vernaculars": []})
        if "article" in binding and fields["title"] is None:
            fields["title"] = _title(binding["article"]["value"])
        if "vn" in binding:
            vn = binding["vn"]["value"]
            if vn not in fields["vernaculars"]:
                fields["vernaculars"].append(vn)


def _values(qid: str, fields: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {"wikidata.qid": qid}
    if fields.get("title"):
        values["wikipedia.title"] = fields["title"]
    if fields.get("vernaculars"):
        values["organism.vernacular_names"] = list(fields["vernaculars"])
    return values
