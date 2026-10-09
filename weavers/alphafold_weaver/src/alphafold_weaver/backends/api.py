"""The api backend for alphafold_weaver — the keyless EBI AlphaFold DB REST API.

Strategy: a UniProt ``protein.uniprot.accession`` is sent to
``GET /api/prediction/{accession}``. The endpoint returns a list of models — the
**preferred F1** one (``AF-{accession}-F1``) plus, for some proteins, alternative-isoform
models. The backend picks the representative F1 model (falling back to the lexicographically
smallest entry id) and emits its model file URL, mean pLDDT confidence, PAE plot, and
version, plus a full ``records`` metadata blob (incl. the pLDDT confidence breakdown).

**Determinism:** the F1-first pick is stable within one observed source response.
F1 can be a partial fragment, not a complete protein model. An accession with no
AlphaFold model (404) is a clean ``NO_MATCH``.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (prediction for P04637 -> AF-P04637-F1).
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status, map_bounded
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

logger = logging.getLogger("alphafold_weaver.api")

DEFAULT_BASE_URL = "https://alphafold.ebi.ac.uk"


class _InvalidResponse(ValueError):
    """Expected source schema or correlation failure, rather than a coding fault."""


def _validated_entries(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list):
        raise _InvalidResponse("AlphaFold response must be a list")
    for entry in body:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("entryId"), str)
            or not entry["entryId"]
        ):
            raise _InvalidResponse("AlphaFold entry must contain an entryId")
        for field in ("uniprotStart", "uniprotEnd"):
            value = entry.get(field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 1
            ):
                raise _InvalidResponse(f"AlphaFold {field} must be a positive integer or null")
        for field in ("uniprotSequence", "sequence"):
            if entry.get(field) is not None and not isinstance(entry[field], str):
                raise _InvalidResponse(f"AlphaFold {field} must be a string or null")
        start, end = entry.get("uniprotStart"), entry.get("uniprotEnd")
        sequence = entry.get("uniprotSequence")
        if (
            start is not None
            and end is not None
            and (start > end or (sequence and end > len(sequence)))
        ):
            raise _InvalidResponse("AlphaFold residue range is inconsistent with sequence")
        for field in ("pdbUrl", "cifUrl", "paeImageUrl"):
            if entry.get(field) is not None and not isinstance(entry[field], str):
                raise _InvalidResponse(f"AlphaFold {field} must be a string or null")
        for field in (
            "globalMetricValue",
            "latestVersion",
            "fractionPlddtVeryHigh",
            "fractionPlddtConfident",
            "fractionPlddtLow",
            "fractionPlddtVeryLow",
        ):
            value = entry.get(field)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise _InvalidResponse(f"AlphaFold {field} must be a finite number or null")
    return body


def _pick(entries: list[dict[str, Any]], accession: str) -> dict[str, Any]:
    """Prefer ``AF-{accession}-F1``; F1 may be a partial overlapping fragment."""
    canonical_id = f"AF-{accession}-F1"
    canonical = next((e for e in entries if e.get("entryId") == canonical_id), None)
    return canonical or min(entries, key=lambda e: e.get("entryId") or "")


def _coverage(entry: dict[str, Any]) -> dict[str, Any]:
    start, end = entry.get("uniprotStart"), entry.get("uniprotEnd")
    sequence = entry.get("uniprotSequence")
    length = len(sequence) if sequence else None
    status = "unknown"
    if start is not None and end is not None:
        if start > 1 or (length is not None and end < length):
            status = "partial"
        elif length is not None and start == 1 and end == length:
            status = "full_sequence"
    fragment = re.search(r"-F(\d+)$", entry["entryId"])
    return {
        "uniprot_start": start,
        "uniprot_end": end,
        "sequence_length": length,
        "model_length": end - start + 1 if start is not None and end is not None else None,
        "fragment_number": int(fragment[1]) if fragment else None,
        "status": status,
    }


def _extract(entry: dict[str, Any]) -> dict[str, Any]:
    """Map one AlphaFold prediction entry to produced type_ids (omitting absent fields)."""
    records = {
        "entry_id": entry.get("entryId"),
        "coverage": _coverage(entry),
        "mean_plddt": entry.get("globalMetricValue"),
        "version": entry.get("latestVersion"),
        "model_url": entry.get("pdbUrl"),
        "cif_url": entry.get("cifUrl"),
        "pae_image_url": entry.get("paeImageUrl"),
        "plddt": {
            "very_high": entry.get("fractionPlddtVeryHigh"),
            "confident": entry.get("fractionPlddtConfident"),
            "low": entry.get("fractionPlddtLow"),
            "very_low": entry.get("fractionPlddtVeryLow"),
        },
    }
    candidates: dict[str, Any] = {
        "structure.alphafold.entry_id": entry.get("entryId"),
        "structure.alphafold.mean_plddt": entry.get("globalMetricValue"),
        "structure.alphafold.model_url": entry.get("pdbUrl"),
        "structure.alphafold.pae_image_url": entry.get("paeImageUrl"),
        "structure.alphafold.version": entry.get("latestVersion"),
        "structure.alphafold.records": records,
    }
    return {k: v for k, v in candidates.items() if v is not None}


class AlphafoldApiBackend(HTTPClientLifecycle, BackendBase):
    """AlphaFold DB REST backend. Always configured — the API is free, no key."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        max_concurrency: int = 4,
    ) -> None:
        self._configure_client(client, base_url)
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self._max_concurrency = max_concurrency

    def is_configured(self) -> bool:
        """AlphaFold DB REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the REST API contract."""
        return remote_fingerprint(
            "alphafold_weaver-api", self._base_url, contract="alphafold-api-v1"
        )

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return PacedHTTPClient(self._client, "alphafold")

    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
        params: dict[str, Any] | None = None,
    ) -> list[LookupRecord]:
        async def resolve(query: dict[str, Any]) -> LookupRecord:
            return await self._resolve_one(
                query, str(query.get("protein.uniprot.accession") or "").strip()
            )

        return await map_bounded(queries, resolve, limit=self._max_concurrency)

    async def _resolve_one(self, query: dict[str, Any], accession: str) -> LookupRecord:
        if not accession:
            return LookupRecord(query=query, found=False)
        try:
            resp = await self._http().get(f"/api/prediction/{accession}")
            resp.raise_for_status()
            entries = _validated_entries(resp.json())
        except httpx.HTTPStatusError as exc:
            # AlphaFold returns 400 for a malformed/unmappable accession and 404 for none —
            # both are "no model", a NO_MATCH, not an error. (Coverage is near-universal, so
            # a well-formed accession almost always has a model.)
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("AlphaFold lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"AlphaFold API error: {format_exc(exc)}")
        except (
            httpx.HTTPError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            _InvalidResponse,
        ) as exc:  # expected source failures are values
            logger.warning("AlphaFold lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"AlphaFold API error: {format_exc(exc)}")

        if not entries:
            return LookupRecord(query=query, found=False)
        selected = _pick(entries, accession)
        values = _extract(selected)
        coverage = values["structure.alphafold.records"]["coverage"]
        warnings = []
        if coverage["status"] == "partial":
            warnings.append(
                "Selected AlphaFold model covers a partial sequence fragment; F1 does not imply full protein coverage"
            )
        return LookupRecord(query=query, found=True, values=values, warnings=tuple(warnings))
