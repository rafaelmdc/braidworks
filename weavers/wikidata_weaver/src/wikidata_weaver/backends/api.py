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

import asyncio
import json
import math
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import unquote

import httpx
from braidworks.core import (
    BackendBase,
    Candidate,
    MatchStatus,
    ResolverRecord,
)
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

# The Wikidata Query Service SPARQL endpoint (distinct from the www. content host).
BASE_URL = "https://query.wikidata.org"
_USER_AGENT = "Braidworks (https://github.com/rafaelmdc/braidworks)"

# Resolve P225 (taxon name) -> item, optional enwiki sitelink, and every English
# name we can use for the alias index, UNIONed into ?vn (no label×alias cross-product):
#   rdfs:label, skos:altLabel, P1843 taxon common names, and the label of any separate
#   "common name of a group of organisms" item that points here via P13176 ("taxon
#   known by this common name") — the latter is how "seal"/"monkey"/"kangaroo" resolve,
#   since they live on a vernacular item, not the family.
# wikibase:sitelinks is the item's total sitelink count — a language-reach proxy used
# as the FALLBACK "fame" signal for taxa with no enwiki article (so no pageviews).
# ?rank (P105 taxon rank, English label) is pulled so a caller can disambiguate a
# cross-code homonym — the same scientific name on several items (e.g. "Pholidota" is
# both an orchid genus and the pangolin order) — by the expected rank. It's a direct
# property (cheap), unlike a P171* kingdom-closure (which times out at batch scale).
# ?sname is echoed so we can align rows back to the input batch.
_SPARQL = """
SELECT ?sname ?item ?article ?sitelinks ?vn ?rankLabel WHERE {{
  VALUES ?sname {{ {values} }}
  ?item wdt:P225 ?sname .
  OPTIONAL {{ ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }}
  OPTIONAL {{ ?item wikibase:sitelinks ?sitelinks . }}
  OPTIONAL {{ ?item wdt:P105 ?rank . ?rank rdfs:label ?rankLabel . FILTER(LANG(?rankLabel) = "en") }}
  OPTIONAL {{
    {{ ?item rdfs:label ?vn . }} UNION {{ ?item skos:altLabel ?vn . }}
    UNION {{ ?item wdt:P1843 ?vn . }}
    UNION {{ ?cn wdt:P13176 ?item . ?cn rdfs:label ?vn . }}
    FILTER(LANG(?vn) = "en")
  }}
}}
"""


def _qid(item_uri: str) -> str:
    return item_uri.rsplit("/", 1)[-1]


def _title(article_uri: str) -> str:
    # https://en.wikipedia.org/wiki/Brown_bear -> "Brown_bear" (pageviews-ready form)
    return unquote(article_uri.rsplit("/wiki/", 1)[-1])


def _sparql_literal(value: str) -> str:
    # JSON string escapes are also valid SPARQL short-string escapes, including
    # newline/tab/control characters which must never appear literally in VALUES.
    return json.dumps(value, ensure_ascii=True)


# Names per SPARQL request. The batch is POSTed (no URL-length limit) and split into
# chunks so a single query stays well within the query service's time/size budget.
_CHUNK = 200

# WDQS is flaky under batch load — it intermittently times out, 429/503s, or (the nasty
# one) returns HTTP 200 with a truncated/garbled body that isn't valid JSON. Retry a chunk a
# few times with exponential backoff before giving up, so a transient hiccup neither crashes
# the build nor silently drops a whole chunk's enrichment.
_MAX_ATTEMPTS = 4
_BACKOFF_BASE = 0.5  # seconds: 0.5, 1, 2 between attempts
_RETRY_STATUS = {429, 500, 502, 503, 504}


_RETRY_BUDGET = 90.0  # elapsed seconds per chunk, including server-advised waits


class _InvalidResponse(ValueError):
    """A malformed or uncorrelatable SPARQL source response."""


def _validated_payload(body: Any) -> dict[str, Any]:
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("results"), dict)
        or not isinstance(body["results"].get("bindings"), list)
    ):
        raise _InvalidResponse("SPARQL response must contain results.bindings")
    for binding in body["results"]["bindings"]:
        if not isinstance(binding, dict):
            raise _InvalidResponse("SPARQL binding must be an object")
        for key in ("sname", "item"):
            if key not in binding:
                raise _InvalidResponse(f"SPARQL binding must contain {key}")
        for key in ("sname", "item", "article", "sitelinks", "vn", "rankLabel"):
            if key in binding and (
                not isinstance(binding[key], dict) or not isinstance(binding[key].get("value"), str)
            ):
                raise _InvalidResponse(f"SPARQL {key} binding must contain a string value")
        if not re.fullmatch(
            r"https?://www\.wikidata\.org/entity/Q[1-9][0-9]*", binding["item"]["value"]
        ):
            raise _InvalidResponse("SPARQL item must be a Wikidata entity URI")
        if "article" in binding and not binding["article"]["value"].startswith(
            "https://en.wikipedia.org/wiki/"
        ):
            raise _InvalidResponse("SPARQL article must be an English Wikipedia URI")
        if "sitelinks" in binding and not binding["sitelinks"]["value"].isdigit():
            raise _InvalidResponse("SPARQL sitelinks must be a non-negative integer")
    return body


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


class _ChunkFailed(Exception):
    """A chunk that exhausted its retries — its names are marked ERROR, others are unaffected."""


class WikidataApiBackend(HTTPClientLifecycle, BackendBase):
    """api backend — calls the keyless Wikidata Query Service."""

    name = "api"

    def __init__(
        self, *, base_url: str = BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._configure_client(client, base_url)
        self._configured = True  # keyless service — always usable

    def is_configured(self) -> bool:
        return self._configured or self._client is not None

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=60.0)
        return PacedHTTPClient(self._client, "wikidata")

    def fingerprint(self) -> str:
        # Wikidata is continuously edited; bucket the cache by query month so results
        # refresh monthly (matches the spec's "query-month" source of truth).
        return remote_fingerprint(
            "wikidata_weaver-api",
            self._base_url,
            contract="wikidata-api-" + datetime.now(UTC).strftime("%Y-%m"),
        )

    async def _post_chunk(self, query: str) -> dict[str, Any]:
        """POST one chunk and return the parsed SPARQL JSON, retrying transient failures.

        SPARQL 400/404 are service/query errors, not biological absence. Honor
        Retry-After within an elapsed budget; cancellation propagates unchanged."""
        last = "unknown error"
        deadline = time.monotonic() + _RETRY_BUDGET
        for attempt in range(_MAX_ATTEMPTS):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                last = f"retry elapsed budget exhausted: {last}"
                break
            delay = _BACKOFF_BASE * (2**attempt)
            try:
                # POST (not GET) so a large VALUES batch isn't capped by URL length.
                async with asyncio.timeout(remaining):
                    resp = await self._http().post(
                        "/sparql",
                        data={"query": query, "format": "json"},
                        timeout=min(60.0, remaining),
                        headers={
                            "Accept": "application/sparql-results+json",
                            "User-Agent": _USER_AGENT,
                        },
                    )
                resp.raise_for_status()
                return _validated_payload(resp.json())
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                last = f"HTTP {code}"
                if code not in _RETRY_STATUS:
                    break
                advice = _retry_after(exc.response.headers.get("Retry-After"))
                if advice is not None:
                    delay = max(delay, advice)
            except TimeoutError:
                last = "retry elapsed budget exhausted during request"
                break
            except httpx.HTTPError as exc:  # timeouts, connection resets, …
                last = str(exc)
            except (json.JSONDecodeError, UnicodeDecodeError, _InvalidResponse) as exc:
                last = f"malformed response: {exc}"
            if attempt < _MAX_ATTEMPTS - 1:
                if delay >= deadline - time.monotonic():
                    last = f"retry wait exceeds elapsed budget: {last}"
                    break
                await asyncio.sleep(delay)
        raise _ChunkFailed(last)

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
        # A chunk that exhausts its retries marks ONLY its own names ERROR — a transient WDQS
        # failure must not nuke the enrichment of every other name in the batch.
        failed: dict[str, str] = {}

        for start in range(0, len(distinct), _CHUNK):
            chunk = distinct[start : start + _CHUNK]
            query = _SPARQL.format(values=" ".join(_sparql_literal(n) for n in chunk))
            try:
                payload = await self._post_chunk(query)
                if any(
                    binding["sname"]["value"] not in chunk
                    for binding in payload["results"]["bindings"]
                ):
                    raise _ChunkFailed("SPARQL response contains an unrequested name")
                _accumulate(payload, rows_by_name)
            except _ChunkFailed as exc:
                failed.update(dict.fromkeys(chunk, str(exc)))

        # Optional disambiguator: when a name resolves to several items, prefer the one
        # whose taxon rank (P105) matches this. Omitted (default) → historical behaviour.
        expected_rank = str((params or {}).get("expected_rank") or "").strip().lower()

        records: list[ResolverRecord] = []
        for name, query in zip(names, queries):
            if name in failed:
                records.append(
                    ResolverRecord(
                        query=query,
                        status=MatchStatus.ERROR,
                        values={},
                        candidates=[],
                        error=f"Wikidata query failed: {failed[name]}",
                    )
                )
                continue
            items = rows_by_name.get(name, {})
            conflicts = {
                qid: fields["conflicts"]
                for qid, fields in sorted(items.items())
                if fields.get("conflicts")
            }
            if conflicts:
                records.append(
                    ResolverRecord(
                        query=query,
                        status=MatchStatus.ERROR,
                        values={},
                        candidates=[],
                        error="Conflicting Wikidata bindings: "
                        + json.dumps(conflicts, sort_keys=True),
                    )
                )
                continue
            # Homonym across nomenclature codes ("Pholidota" = orchid genus + pangolin
            # order): if the caller told us the expected rank and exactly one candidate
            # has it, collapse to that one — a single RESOLVED instead of AMBIGUOUS.
            if len(items) > 1 and expected_rank:
                ranked = {
                    qid: fields
                    for qid, fields in items.items()
                    if (fields.get("rank") or "").lower() == expected_rank
                }
                if len(ranked) == 1:
                    items = ranked
            if not items:
                records.append(
                    ResolverRecord(
                        query=query, status=MatchStatus.NO_MATCH, values={}, candidates=[]
                    )
                )
            elif len(items) == 1:
                ((qid, fields),) = items.items()
                records.append(
                    ResolverRecord(
                        query=query,
                        status=MatchStatus.RESOLVED,
                        values=_values(qid, fields),
                        candidates=[],
                    )
                )
            else:
                # Same scientific name on several items (homonym across nomenclature
                # codes, or duplicate items) — return all for review, deterministically.
                candidates = [
                    Candidate(values=_values(qid, fields)) for qid, fields in sorted(items.items())
                ]
                records.append(
                    ResolverRecord(
                        query=query, status=MatchStatus.AMBIGUOUS, values={}, candidates=candidates
                    )
                )
        return records


def _accumulate(
    payload: dict[str, Any], rows_by_name: dict[str, dict[str, dict[str, Any]]]
) -> None:
    """Collect all observed values before projecting a scalar; never choose first."""
    for binding in payload.get("results", {}).get("bindings", []):
        sname = binding["sname"]["value"]
        qid = _qid(binding["item"]["value"])
        fields = rows_by_name[sname].setdefault(
            qid,
            {
                "title": None,
                "sitelinks": None,
                "vernaculars": [],
                "rank": None,
                "observed": {},
                "conflicts": {},
            },
        )
        for source, target, transform in (
            ("article", "title", _title),
            ("sitelinks", "sitelinks", int),
            ("rankLabel", "rank", str),
        ):
            if source in binding:
                observed = fields["observed"].setdefault(target, set())
                observed.add(transform(binding[source]["value"]))
                ordered = sorted(observed)
                fields[target] = ordered[0] if len(ordered) == 1 else None
                if len(ordered) > 1:
                    fields["conflicts"][target] = ordered
        if "vn" in binding:
            fields["vernaculars"] = sorted(set(fields["vernaculars"]) | {binding["vn"]["value"]})


def _values(qid: str, fields: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {"wikidata.qid": qid}
    if fields.get("title"):
        values["wikipedia.title"] = fields["title"]
    if fields.get("sitelinks") is not None:
        values["wikidata.sitelinks"] = fields["sitelinks"]
    if fields.get("vernaculars"):
        values["organism.vernacular_names"] = list(fields["vernaculars"])
    return values
