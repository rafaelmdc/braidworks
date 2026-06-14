"""The api backend for alphafold_weaver — the keyless EBI AlphaFold DB REST API.

Strategy: a UniProt ``protein.uniprot.accession`` is sent to
``GET /api/prediction/{accession}``. The endpoint returns a list of models — the
**canonical** one (``AF-{accession}-F1``) plus, for some proteins, alternative-isoform
models. The backend picks the canonical model (falling back to the lexicographically
smallest entry id) and emits its model file URL, mean pLDDT confidence, PAE plot, and
version, plus a full ``records`` metadata blob (incl. the pLDDT confidence breakdown).

**Determinism:** the canonical-first pick means the same accession always yields the
same model. An accession with no AlphaFold model (404) is a clean ``NO_MATCH``.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport`` offline (see ``fixture.py``). The JSON shape was validated
against the live API (prediction for P04637 -> AF-P04637-F1).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from braidworks.core import BackendBase, LookupRecord, is_not_found_status

logger = logging.getLogger("alphafold_weaver.api")

DEFAULT_BASE_URL = "https://alphafold.ebi.ac.uk"


def _pick(entries: list[dict[str, Any]], accession: str) -> dict[str, Any]:
    """The canonical model ``AF-{accession}-F1`` if present, else the lowest entry id."""
    canonical_id = f"AF-{accession}-F1"
    canonical = next((e for e in entries if e.get("entryId") == canonical_id), None)
    return canonical or min(entries, key=lambda e: e.get("entryId") or "")


def _extract(entry: dict[str, Any]) -> dict[str, Any]:
    """Map one AlphaFold prediction entry to produced type_ids (omitting absent fields)."""
    records = {
        "entry_id": entry.get("entryId"),
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


class AlphafoldApiBackend(BackendBase):
    """AlphaFold DB REST backend. Always configured — the API is free, no key."""

    name = "api"

    def __init__(
        self, *, base_url: str = DEFAULT_BASE_URL, client: httpx.AsyncClient | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client

    def is_configured(self) -> bool:
        """AlphaFold DB REST needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """A live service; the fingerprint pins the REST API contract."""
        return "alphafold-api-v1"

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
        records: list[LookupRecord] = []
        for query in queries:
            accession = str(query.get("protein.uniprot.accession", "")).strip()
            records.append(await self._resolve_one(query, accession))
        return records

    async def _resolve_one(self, query: dict[str, Any], accession: str) -> LookupRecord:
        if not accession:
            return LookupRecord(query=query, found=False)
        try:
            resp = await self._http().get(f"/api/prediction/{accession}")
            resp.raise_for_status()
            entries = resp.json()
        except httpx.HTTPStatusError as exc:
            # AlphaFold returns 400 for a malformed/unmappable accession and 404 for none —
            # both are "no model", a NO_MATCH, not an error. (Coverage is near-universal, so
            # a well-formed accession almost always has a model.)
            if is_not_found_status(exc.response.status_code):
                return LookupRecord(query=query, found=False)
            logger.warning("AlphaFold lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"AlphaFold API error: {exc}")
        except httpx.HTTPError as exc:  # network/timeout problem is a per-entity error
            logger.warning("AlphaFold lookup failed for %r: %s", accession, exc)
            return LookupRecord(query=query, error=f"AlphaFold API error: {exc}")

        if not isinstance(entries, list) or not entries:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_extract(_pick(entries, accession)))
