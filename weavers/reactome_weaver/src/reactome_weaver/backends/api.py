"""The api backend for reactome_weaver — the keyless Reactome ContentService API.

Strategy: a UniProt ``protein.uniprot.accession`` is sent to
``GET /data/mapping/UniProt/{accession}/pathways``. Reactome resolves the accession to
its protein + species itself and returns the pathways it participates in. The backend
dedups to **distinct pathways** (by Reactome stable id), orders them by stable id, and
emits ``pathway.reactome.id`` (every distinct stId — the one→many fan dimension),
``pathway.reactome.names`` (top ``limit``), ``pathway.reactome.count`` (true total),
and ``pathway.reactome.records`` (``{st_id, name, in_disease}``).

**Determinism:** fixed ordering applies to the same observed response; live source
updates can change pathways. Conflicting duplicate stable IDs are source errors.
An accession with no pathways (Reactome 404/400, or an empty list) is a clean ``NO_MATCH``.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (mapping/UniProt/P04637/pathways).
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status, map_bounded
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

logger = logging.getLogger("reactome_weaver.api")

DEFAULT_BASE_URL = "https://reactome.org/ContentService"
DEFAULT_LIMIT = 30  # top pathways to surface in names/records (count stays the true total)
_ID_CHUNK = 100  # pathway ids per POST /data/query/ids request (keeps the body bounded)


class _InvalidResponse(ValueError):
    """Expected source schema or correlation failure, rather than a coding fault."""


def _validated_rows(body: Any, requested: list[str] | None = None) -> list[dict[str, Any]]:
    """Keep source schema and correlation rules at the Reactome boundary."""
    if not isinstance(body, list):
        raise _InvalidResponse("Reactome response must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for row in body:
        if not isinstance(row, dict) or not isinstance(row.get("stId"), str) or not row["stId"]:
            raise _InvalidResponse("Reactome row must contain a stable identifier")
        if requested is not None and row["stId"] not in requested:
            raise _InvalidResponse("Reactome response contains an unrequested identifier")
        for field in ("displayName", "speciesName", "releaseDate", "schemaClass"):
            if row.get(field) is not None and not isinstance(row[field], str):
                raise _InvalidResponse(f"Reactome {field} must be a string or null")
        for field in ("isInDisease", "isInferred"):
            if row.get(field) is not None and not isinstance(row[field], bool):
                raise _InvalidResponse(f"Reactome {field} must be a boolean or null")
        previous = by_id.setdefault(row["stId"], row)
        if previous != row:
            raise _InvalidResponse(f"Conflicting Reactome rows for {row['stId']}")
    return body


def _extract(rows: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    """Dedup pathway rows to distinct pathways (by stId) and order by stId."""
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        st_id = raw.get("stId")
        if not st_id or st_id in by_id:
            continue
        by_id[st_id] = {
            "st_id": st_id,
            "name": raw.get("displayName"),
            "in_disease": raw.get("isInDisease"),
            "species": raw.get("speciesName"),
            "is_inferred": raw.get("isInferred"),
            "source": deepcopy(raw),
        }
    records = sorted(by_id.values(), key=lambda p: p["st_id"])
    top = records[:limit]
    return {
        # The fan dimension (set_outputs): every distinct pathway stId, so a caller can
        # fan out one child per pathway. Uncapped — names/records below are the top-N
        # display; the executor's max_expansion bounds any runaway.
        "pathway.reactome.id": [r["st_id"] for r in records],
        "pathway.reactome.names": [r["name"] for r in top if r["name"]],
        "pathway.reactome.count": len(by_id),  # true total distinct; names/records are top N
        "pathway.reactome.records": top,
    }


def _hierarchy(obj: dict[str, Any]) -> dict[str, Any]:
    events = obj.get("hasEvent")
    if events is not None:
        events = _validated_rows(events)
    return {
        "id": obj["stId"],
        "type": obj.get("schemaClass"),
        "children": sorted(
            [
                {"id": row["stId"], "type": row.get("schemaClass"), "name": row.get("displayName")}
                for row in {row["stId"]: row for row in events or []}.values()
            ],
            key=lambda row: row["id"],
        )
        if events is not None
        else None,
        "scope": "direct hasEvent children only; no recursive expansion or inferred parents",
    }


def _participants(body: Any, pid: str, release: int) -> dict[str, Any]:
    if not isinstance(body, list):
        raise _InvalidResponse("Reactome participants must be a list")
    rows = {}
    for row in body:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("schemaClass"), str)
            or isinstance(row.get("peDbId"), bool)
            or not isinstance(row.get("peDbId"), int)
        ):
            raise _InvalidResponse("Reactome participant must have a typed provider ID")
        references = row.get("refEntities")
        if references is not None and (
            not isinstance(references, list) or any(not isinstance(ref, dict) for ref in references)
        ):
            raise _InvalidResponse("Reactome participant references must be objects")
        key = row["peDbId"]
        if key in rows and rows[key]["source"] != row:
            raise _InvalidResponse("Conflicting Reactome participant identity")
        rows[key] = {
            "physical_entity_id": key,
            "observed_release": release,
            "type": row["schemaClass"],
            "name": row.get("displayName"),
            "references": deepcopy(references) if references is not None else None,
            "source": deepcopy(row),
        }
    return {
        "event_id": pid,
        "observed_release": release,
        "records": [rows[key] for key in sorted(rows)],
        "scope": "provider event participants; numeric IDs are scoped to the observed release, entity types retained",
    }


def _describe(obj: dict[str, Any]) -> dict[str, Any]:
    """One Reactome pathway object (/data/query/{id}) -> describe_pathway outputs."""
    return {
        "pathway.reactome.display_name": obj.get("displayName"),
        "pathway.reactome.species": obj.get("speciesName"),
        "pathway.reactome.in_disease": obj.get("isInDisease"),
        "pathway.reactome.detail": {
            "st_id": obj.get("stId"),
            "display_name": obj.get("displayName"),
            "species": obj.get("speciesName"),
            "in_disease": obj.get("isInDisease"),
            "release_date": obj.get("releaseDate"),
            "schema_class": obj.get("schemaClass"),
        },
    }


class ReactomeApiBackend(HTTPClientLifecycle, BackendBase):
    """Reactome ContentService backend. Always configured — the API is free, no key."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        limit: int = DEFAULT_LIMIT,
        max_concurrency: int = 4,
    ) -> None:
        self._configure_client(client, base_url)
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self._max_concurrency = max_concurrency
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        self._limit = limit

    def is_configured(self) -> bool:
        """Reactome ContentService needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """Identify the effective endpoint and result-affecting policy, not live contents."""
        endpoint = (
            str(self._client.base_url)
            if self._client is not None and str(self._client.base_url)
            else self._base_url
        )
        return remote_fingerprint("reactome-api", endpoint, limit=self._limit)

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url, timeout=30.0, headers={"Accept": "application/json"}
            )
        return PacedHTTPClient(self._client, "reactome")

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        # describe_pathway drills pathway ids; list_pathways lists a protein's pathways.
        if capability_id == "describe_pathway":
            return await self._describe_pathways(queries, groups=groups_to_compute)

        async def resolve(query: dict[str, Any]) -> LookupRecord:
            return await self._resolve_one(
                query, str(query.get("protein.uniprot.accession", "")).strip()
            )

        return await map_bounded(queries, resolve, limit=self._max_concurrency)

    async def _describe_pathways(
        self, queries: list[dict[str, Any]], *, groups: frozenset[str] = frozenset()
    ) -> list[LookupRecord]:
        """Pathway ids -> their details via the bulk ``POST /data/query/ids`` endpoint.

        The whole batch is sent as a comma-separated id list (chunked) instead of one
        ``GET /data/query/{id}`` per pathway; the response is a list of objects keyed
        back by ``stId``.
        """
        pids = [str(q.get("pathway.reactome.id", "")).strip() for q in queries]
        distinct = sorted({p for p in pids if p})
        objs: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        for start in range(0, len(distinct), _ID_CHUNK):
            chunk = distinct[start : start + _ID_CHUNK]
            try:
                resp = await self._http().post(
                    "/data/query/ids",
                    content=",".join(chunk),
                    headers={"Content-Type": "text/plain"},
                )
                resp.raise_for_status()
                rows = _validated_rows(resp.json(), chunk)
                objs.update({obj["stId"]: obj for obj in rows})
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    errors.update(dict.fromkeys(chunk, f"Reactome API error: {format_exc(exc)}"))
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                errors.update(dict.fromkeys(chunk, f"Reactome API error: {format_exc(exc)}"))

        participant_values = {}
        if "participants" in groups and objs:
            try:
                response = await self._http().get("/data/database/version", headers={"Accept": "text/plain"})
                response.raise_for_status()
                release = int(response.text.strip())
                if release < 1:
                    raise ValueError("nonpositive release")
            except (httpx.HTTPError, ValueError) as exc:
                errors.update(
                    dict.fromkeys(objs, f"Reactome release unavailable: {format_exc(exc)}")
                )
            else:

                async def fetch_participants(
                    pid: str,
                ) -> tuple[str, dict[str, Any] | None, str | None]:
                    try:
                        response = await self._http().get(f"/data/participants/{pid}")
                        response.raise_for_status()
                        return pid, _participants(response.json(), pid, release), None
                    except httpx.HTTPStatusError as exc:
                        if is_not_found_status(exc.response.status_code):
                            return (
                                pid,
                                {
                                    "event_id": pid,
                                    "observed_release": release,
                                    "records": None,
                                    "available": False,
                                },
                                None,
                            )
                        return pid, None, f"Reactome participants error: {format_exc(exc)}"
                    except (
                        httpx.HTTPError,
                        json.JSONDecodeError,
                        UnicodeDecodeError,
                        _InvalidResponse,
                    ) as exc:
                        return pid, None, f"Reactome participants error: {format_exc(exc)}"

                results = await map_bounded(
                    sorted(objs), fetch_participants, limit=self._max_concurrency
                )
                for pid, value, error in results:
                    if error:
                        errors[pid] = error
                    else:
                        participant_values[pid] = value
        records: list[LookupRecord] = []
        for query, pid in zip(queries, pids):
            obj = objs.get(pid) if pid else None
            if pid in errors:
                records.append(LookupRecord(query=query, error=errors[pid]))
            elif not obj:
                records.append(LookupRecord(query=query, found=False))
            else:
                values = _describe(obj)
                try:
                    if "hierarchy" in groups:
                        values["pathway.reactome.hierarchy"] = _hierarchy(obj)
                    if "participants" in groups:
                        values["pathway.reactome.participants"] = deepcopy(participant_values[pid])
                except _InvalidResponse as exc:
                    records.append(LookupRecord(query=query, error=str(exc)))
                else:
                    records.append(LookupRecord(query=query, found=True, values=values))
        return records

    async def _resolve_one(self, query: dict[str, Any], accession: str) -> LookupRecord:
        if not accession:
            return LookupRecord(query=query, found=False)
        try:
            resp = await self._http().get(f"/data/mapping/UniProt/{accession}/pathways")
            resp.raise_for_status()
            rows = _validated_rows(resp.json())
        except httpx.HTTPStatusError as exc:
            # Reactome 404/400s an accession it can't map to pathways — a NO_MATCH, not error.
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("Reactome lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"Reactome API error: {format_exc(exc)}")
        except (
            httpx.HTTPError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            _InvalidResponse,
        ) as exc:  # expected source failures are values
            logger.warning("Reactome lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"Reactome API error: {format_exc(exc)}")

        if not rows:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_extract(rows, self._limit))
