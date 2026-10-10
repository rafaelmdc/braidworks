"""The api backend for pdbe_weaver — the keyless EBI PDBe REST API.

Strategy: a UniProt ``protein.uniprot.accession`` is sent to
``GET /pdbe/api/mappings/best_structures/{accession}``. PDBe returns one row per
(structure, chain) mapping, so a protein yields many rows. The backend:
  * **dedups to distinct PDB structures** (``pdb_id``), keeping the best-covering chain;
  * orders them best-first — coverage descending, then resolution ascending, then pdb_id;
  * emits ``structure.pdb.ids`` (top ``limit``), ``structure.pdb.count`` (total distinct),
    and ``structure.pdb.records`` (top ``limit`` with method/resolution/coverage).

**Determinism:** the fixed sort means the same accession always yields the same list.
An accession with no structures (PDBe 404, or an empty mapping) is a clean ``NO_MATCH``.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (best_structures for P04637).
"""

from __future__ import annotations

import json
import logging
import math
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import replace
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status, map_bounded
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

from pdbe_weaver.structure_detail import (
    SIFTS_COMPRESSED_LIMIT,
    DetailFormatError,
    coordinate_artifacts,
    sifts_residues,
    source_detail,
)

logger = logging.getLogger("pdbe_weaver.api")

DEFAULT_BASE_URL = "https://www.ebi.ac.uk/pdbe/api"
DEFAULT_LIMIT = 25  # top structures to surface in ids/records (count stays the true total)
_BEST_CHUNK = 100  # accessions per bulk best-structure request
_SUMMARY_CHUNK = 200  # pdb ids per POST /pdb/entry/summary request (keeps the body bounded)
_WORST_RESOLUTION = 1e9  # sort sentinel for entries with no resolution (NMR/EM sometimes)


class _InvalidResponse(ValueError):
    """Expected source schema or correlation failure, rather than a coding fault."""


def _validated_mapping(body: Any, requested: list[str], *, summaries: bool = False) -> dict:
    """Validate the keyed PDBe envelope before projecting source rows."""
    if not isinstance(body, dict):
        raise _InvalidResponse("PDBe response must be an object keyed by requested identifier")
    expected = {key.upper() for key in requested}
    result = {}
    for key, rows in body.items():
        if key.upper() not in expected:
            raise _InvalidResponse("PDBe response contains an unrequested identifier")
        if not isinstance(rows, list):
            raise _InvalidResponse("PDBe identifier rows must be a list")
        for row in rows:
            if not isinstance(row, dict):
                raise _InvalidResponse("PDBe row must be an object")
            if summaries:
                if not isinstance(row.get("title"), str) or not row["title"]:
                    raise _InvalidResponse("PDBe summary must contain a title")
                method = row.get("experimental_method", [])
                if not isinstance(method, list) or any(not isinstance(m, str) for m in method):
                    raise _InvalidResponse("PDBe summary methods must be a string list")
            else:
                if not isinstance(row.get("pdb_id"), str) or not row["pdb_id"]:
                    raise _InvalidResponse("PDBe mapping must contain a PDB identifier")
                for field in ("coverage", "resolution"):
                    value = row.get(field)
                    if value is not None and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                    ):
                        raise _InvalidResponse(f"PDBe {field} must be a finite number or null")
        result[key.upper()] = rows
    return result


def _record(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "pdb_id": raw.get("pdb_id"),
        "method": raw.get("experimental_method"),
        "resolution": raw.get("resolution"),
        "coverage": raw.get("coverage"),
        "chain_id": raw.get("chain_id"),
        "ranges": {
            "uniprot": {
                "start": raw.get("unp_start"),
                "end": raw.get("unp_end"),
                "namespace": "UniProt residue position",
            },
            "structure": {
                "start": raw.get("start"),
                "end": raw.get("end"),
                "namespace": "PDBe best_structures reported start/end; author numbering not inferred",
            },
            "interpretation": "observed coverage span, not a residue alignment",
        },
        "source": dict(raw),
    }


def _sort_key(rec: dict[str, Any]) -> tuple[float, float, str]:
    """Best-first total order: coverage desc, resolution asc, then pdb_id (stable)."""
    return (
        -(rec.get("coverage") or 0.0),
        rec.get("resolution") or _WORST_RESOLUTION,
        rec.get("pdb_id") or "",
    )


def _extract(rows: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    """Dedup PDBe (structure, chain) rows to distinct best structures, ordered."""
    chains: dict[str, dict[str, dict[str, Any]]] = {}
    for raw in rows:
        pid = raw.get("pdb_id")
        if pid:
            serialized = json.dumps(raw, sort_keys=True, separators=(",", ":"))
            chains.setdefault(pid, {})[serialized] = _record(raw)
    by_id: dict[str, dict[str, Any]] = {}
    for pid, evidence in chains.items():
        # Scientific ranking is unchanged; chain ID and complete source evidence
        # break equal-rank ties independently of upstream row order.
        ordered_chains = sorted(
            evidence.values(),
            key=lambda rec: (
                *_sort_key(rec),
                str(rec.get("chain_id") or ""),
                json.dumps(rec["source"], sort_keys=True, separators=(",", ":")),
            ),
        )
        representative = dict(ordered_chains[0])
        representative["chains"] = ordered_chains
        by_id[pid] = representative
    ordered = sorted(by_id.values(), key=_sort_key)
    top = ordered[:limit]
    return {
        # The fan dimension (set_outputs): every distinct PDB id, so a caller can fan out
        # one child per structure. Uncapped — structure.pdb.ids/records are the top-N
        # display; the executor's max_expansion bounds any runaway.
        "pdb.id": [r["pdb_id"] for r in ordered],
        "structure.pdb.ids": [r["pdb_id"] for r in top],
        "structure.pdb.count": len(by_id),  # true total distinct; ids/records are the top N
        "structure.pdb.records": top,
    }


def _describe(pdb_id: str, obj: dict[str, Any]) -> dict[str, Any]:
    """One PDBe entry summary (/pdb/entry/summary/{id}) -> describe_structure outputs."""
    method = obj.get("experimental_method") or []
    return {
        "structure.pdb.title": obj.get("title"),
        "structure.pdb.method": method[0] if method else None,
        "structure.pdb.release_date": obj.get("release_date"),
        "structure.pdb.detail": {
            "pdb_id": pdb_id,
            "title": obj.get("title"),
            "method": method,
            "release_date": obj.get("release_date"),
            "deposition_date": obj.get("deposition_date"),
            "authors": obj.get("entry_authors"),
        },
    }


class PdbeApiBackend(HTTPClientLifecycle, BackendBase):
    """PDBe REST backend. Always configured — the API is free, no key."""

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
        """PDBe REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """Identify the effective endpoint and result-affecting policy, not live contents."""
        endpoint = (
            str(self._client.base_url)
            if self._client is not None and str(self._client.base_url)
            else self._base_url
        )
        return remote_fingerprint("pdbe-api", endpoint, limit=self._limit)

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return PacedHTTPClient(self._client, "pdbe")

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        # describe_structure drills PDB ids; list_structures lists a protein's structures.
        if capability_id == "describe_structure":
            records = await self._describe_structures(
                queries, quality="quality" in groups_to_compute
            )
            return await self._supplement(records, groups_to_compute)
        return await self._list_structures(queries)

    async def _supplement(self, records, groups):
        endpoints = {
            "entities": "/pdb/entry/molecules",
            "assemblies": "/pdb/entry/assembly",
            "ligands": "/pdb/entry/ligand_monomers",
            "mappings": "/mappings/uniprot",
        }
        ids = sorted(
            {
                str(record.query.get("pdb.id", "")).strip().lower()
                for record in records
                if record.found and not record.error
            }
        )
        details, errors = {}, {}
        selected = set(groups) & set(endpoints)
        if "coordinates" in groups:
            selected.add("assemblies")
        for group in sorted(selected):
            endpoint = endpoints[group]
            details[group] = {}
            if group == "mappings":

                async def acquire_mapping(pid, endpoint=endpoint, group=group):
                    try:
                        response = await self._http().get(f"{endpoint}/{pid}")
                        response.raise_for_status()
                        return pid, source_detail(response.json(), {pid}, group).get(pid), None
                    except httpx.HTTPStatusError as exc:
                        if is_not_found_status(exc.response.status_code):
                            return pid, None, None
                        return pid, None, f"PDBe mapping error: {format_exc(exc)}"
                    except (httpx.HTTPError, ValueError) as exc:
                        return pid, None, f"PDBe mapping error: {format_exc(exc)}"

                for pid, value, error in await map_bounded(ids, acquire_mapping, limit=4):
                    if error:
                        errors[pid] = error
                    elif value is not None:
                        details[group][pid] = value
                continue
            for start in range(0, len(ids), _SUMMARY_CHUNK):
                chunk = ids[start : start + _SUMMARY_CHUNK]
                try:
                    response = await self._http().post(
                        endpoint,
                        content=",".join(chunk),
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    response.raise_for_status()
                    details[group].update(source_detail(response.json(), set(chunk), group))
                except httpx.HTTPStatusError as exc:
                    if not is_not_found_status(exc.response.status_code):
                        errors.update(
                            dict.fromkeys(chunk, f"PDBe {group} error: {format_exc(exc)}")
                        )
                except (httpx.HTTPError, ValueError) as exc:
                    errors.update(dict.fromkeys(chunk, f"PDBe {group} error: {format_exc(exc)}"))
        residues = {}
        if "residues" in groups:

            async def acquire(pid):
                url = f"https://ftp.ebi.ac.uk/pub/databases/msd/sifts/xml/{pid}.xml.gz"
                try:
                    if not re.fullmatch(r"[0-9][a-z0-9]{3}", pid):
                        raise DetailFormatError("SIFTS requires a four-character PDB entry ID")
                    data = bytearray()
                    async with self._http().stream("GET", url) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > SIFTS_COMPRESSED_LIMIT:
                                raise DetailFormatError("SIFTS compressed byte limit exceeded")
                    return pid, sifts_residues(bytes(data), pid, url), None
                except httpx.HTTPStatusError as exc:
                    if is_not_found_status(exc.response.status_code):
                        return pid, None, None
                    return pid, None, f"SIFTS acquisition error: {format_exc(exc)}"
                except (httpx.HTTPError, ValueError, OSError, EOFError, ET.ParseError) as exc:
                    return pid, None, f"SIFTS mapping error: {format_exc(exc)}"

            for pid, value, error in await map_bounded(ids, acquire, limit=4):
                if error:
                    errors[pid] = error
                else:
                    residues[pid] = value
        output = []
        for record in records:
            pid = str(record.query.get("pdb.id", "")).strip().lower()
            if pid in errors:
                output.append(LookupRecord(query=record.query, error=errors[pid]))
                continue
            if not record.found or record.error:
                output.append(record)
                continue
            values = deepcopy(record.values)
            for group in selected & set(groups):
                source = details[group].get(pid)
                values[f"structure.pdb.{group}"] = {
                    "pdb_id": pid,
                    "records": deepcopy(source),
                    "available": source is not None,
                    "source": endpoints[group],
                    "interpretation": "observed source identities and numbering; range endpoints are not a full residue alignment",
                }
            if "residues" in groups:
                values["structure.pdb.residues"] = (
                    deepcopy(residues[pid])
                    if residues[pid] is not None
                    else {"pdb_id": pid, "available": False, "records": None}
                )
            if "coordinates" in groups:
                values["structure.pdb.coordinates"] = coordinate_artifacts(
                    pid, details["assemblies"].get(pid)
                )
            output.append(replace(record, values=values))
        return output

    async def _list_structures(self, queries: list[dict[str, Any]]) -> list[LookupRecord]:
        accessions = [str(q.get("protein.uniprot.accession", "")).strip() for q in queries]
        distinct = sorted({accession for accession in accessions if accession})
        mappings: dict[str, list[dict[str, Any]]] = {}
        errors: dict[str, str] = {}
        for start in range(0, len(distinct), _BEST_CHUNK):
            chunk = distinct[start : start + _BEST_CHUNK]
            try:
                if len(chunk) == 1:
                    response = await self._http().get(f"/mappings/best_structures/{chunk[0]}")
                else:
                    response = await self._http().post(
                        "/mappings/best_structures",
                        content=",".join(chunk),
                        headers={"Content-Type": "text/plain"},
                    )
                response.raise_for_status()
                mappings.update(_validated_mapping(response.json(), chunk))
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    errors.update(dict.fromkeys(chunk, f"PDBe API error: {format_exc(exc)}"))
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                errors.update(dict.fromkeys(chunk, f"PDBe API error: {format_exc(exc)}"))
        records = []
        for query, accession in zip(queries, accessions):
            rows = mappings.get(accession.upper()) or []
            if accession in errors:
                records.append(LookupRecord(query=query, error=errors[accession]))
            elif rows:
                records.append(
                    LookupRecord(query=query, found=True, values=_extract(rows, self._limit))
                )
            else:
                records.append(LookupRecord(query=query, found=False))
        return records

    async def _describe_structures(
        self, queries: list[dict[str, Any]], *, quality: bool = False
    ) -> list[LookupRecord]:
        """PDB ids -> their summaries via the bulk ``POST /pdb/entry/summary`` endpoint.

        The whole batch is sent as a comma-separated id list (chunked to keep the body
        bounded) instead of one ``GET /pdb/entry/summary/{id}`` per structure. PDBe keys
        the response by pdb id, so results are matched back case-insensitively.
        """
        pids = [str(q.get("pdb.id", "")).strip() for q in queries]
        distinct = sorted({p for p in pids if p})
        summaries: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        for start in range(0, len(distinct), _SUMMARY_CHUNK):
            chunk = distinct[start : start + _SUMMARY_CHUNK]
            try:
                resp = await self._http().post(
                    "/pdb/entry/summary",
                    content=",".join(chunk),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
                body = _validated_mapping(resp.json(), chunk, summaries=True)
                summaries.update({key.lower(): rows[0] for key, rows in body.items() if rows})
            except httpx.HTTPStatusError as exc:
                if not is_not_found_status(exc.response.status_code):
                    errors.update(dict.fromkeys(chunk, f"PDBe API error: {format_exc(exc)}"))
            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                _InvalidResponse,
            ) as exc:
                errors.update(dict.fromkeys(chunk, f"PDBe API error: {format_exc(exc)}"))

        quality_rows: dict[str, dict[str, Any]] = {}
        if quality:
            for start in range(0, len(distinct), _SUMMARY_CHUNK):
                chunk = distinct[start : start + _SUMMARY_CHUNK]
                try:
                    resp = await self._http().post(
                        "/validation/summary_quality_scores/entry",
                        content=",".join(chunk),
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    resp.raise_for_status()
                    body = resp.json()
                    if not isinstance(body, dict) or any(
                        key.lower() not in {pid.lower() for pid in chunk}
                        or not isinstance(value, dict)
                        for key, value in body.items()
                    ):
                        raise _InvalidResponse(
                            "PDBe quality response must be keyed by requested entry"
                        )
                    for key, value in body.items():
                        for field in ("geometry_quality", "data_quality", "overall_quality"):
                            metric = value.get(field)
                            if metric is not None and (
                                isinstance(metric, bool)
                                or not isinstance(metric, (float, int))
                                or not math.isfinite(metric)
                            ):
                                raise _InvalidResponse(
                                    "PDBe quality metrics must be finite numbers or null"
                                )
                        quality_rows[key.lower()] = value
                except httpx.HTTPStatusError as exc:
                    if not is_not_found_status(exc.response.status_code):
                        errors.update(
                            dict.fromkeys(chunk, f"PDBe quality error: {format_exc(exc)}")
                        )
                except (
                    httpx.HTTPError,
                    json.JSONDecodeError,
                    UnicodeDecodeError,
                    _InvalidResponse,
                ) as exc:
                    errors.update(dict.fromkeys(chunk, f"PDBe quality error: {format_exc(exc)}"))
        records: list[LookupRecord] = []
        for query, pid in zip(queries, pids):
            obj = summaries.get(pid.lower()) if pid else None
            if pid in errors:
                records.append(LookupRecord(query=query, error=errors[pid]))
            elif obj is None:
                records.append(LookupRecord(query=query, found=False))
            else:
                values = _describe(pid, obj)
                if quality:
                    values["structure.pdb.quality"] = {
                        "pdb_id": pid.lower(),
                        "method": obj.get("experimental_method", []),
                        "metrics": dict(quality_rows[pid.lower()])
                        if pid.lower() in quality_rows
                        else None,
                        "available": pid.lower() in quality_rows,
                        "source": "PDBe validation/summary_quality_scores/entry",
                        "interpretation": "provider entry-level metrics; missing values remain unknown; not a cross-method ranking",
                    }
                records.append(LookupRecord(query=query, found=True, values=values))
        return records
