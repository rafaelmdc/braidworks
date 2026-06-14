"""The api backend for bacdive_weaver — BacDive (DSMZ) v2 REST API.

Strategy (MVP — type strain as the species representative):
  * ``organism.scientific_name`` is split into genus + species epithet and looked
    up via ``GET /taxon/{genus}/{species}``, which returns a paginated list of
    *strain* BacDive IDs (BacDive is strain-level; there is no species summary).
  * IDs are fetched in batches via ``GET /fetch/{id1;id2;...}`` (semicolon-joined,
    ≤100 per call) and we **short-circuit on the first record flagged
    ``type strain == "yes"``** — the nomenclatural representative.
  * That record's phenotype fields are normalized into a ``LookupRecord``.

Cost: there is no "type strains only" filter, so finding the type strain means
scanning records until the flag matches (capped by ``max_strains_scanned``). Batch
fetch keeps that cheap (e.g. E. coli's type strain is ~500 strains in → ~5 calls).
See CONTRIBUTING.md "Expansion notes" for caching and the aggregate / strain-level
modes that lift this MVP's remaining limitations.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport``. JSON paths were validated against real records (fetch/24,
fetch/4409); subfields are a dict for one entry, a list of dicts for many, so every
read goes through ``_first`` / ``_as_list``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from braidworks.core import BackendBase, LookupRecord

logger = logging.getLogger("bacdive_weaver.api")

DEFAULT_BASE_URL = "https://api.bacdive.dsmz.de/v2"
_FETCH_BATCH = 100  # /fetch accepts up to 100 semicolon-joined ids per call


def _as_list(value: Any) -> list[Any]:
    """BacDive subfields are a dict for one entry, a list for many — unify to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first(value: Any) -> dict[str, Any]:
    """First entry of a dict-or-list subfield, as a dict ({} if absent)."""
    items = _as_list(value)
    if items and isinstance(items[0], dict):
        return items[0]
    return {}


def _section(record: dict[str, Any], name: str) -> dict[str, Any]:
    """A top-level BacDive section, collapsed to a single dict."""
    return _first(record.get(name))


def _optimum(entries: Any, value_key: str) -> str | None:
    """From a list of growth-condition entries, the value tagged ``type == optimum``."""
    for entry in _as_list(entries):
        if isinstance(entry, dict) and entry.get("type") == "optimum":
            val = entry.get(value_key)
            if val is not None:
                return str(val)
    return None


def _is_type_strain(record: dict[str, Any]) -> bool:
    taxo = _section(record, "Name and taxonomic classification")
    return str(taxo.get("type strain", "")).strip().lower() == "yes"


def _extract_traits(record: dict[str, Any]) -> dict[str, Any]:
    """Map one BacDive strain record to produced trait type_ids (omitting absent)."""
    morphology = _first(_section(record, "Morphology").get("cell morphology"))
    physiology = _section(record, "Physiology and metabolism")
    oxygen = _first(physiology.get("oxygen tolerance"))
    spore = _first(physiology.get("spore formation"))
    culture = _section(record, "Culture and growth conditions")

    candidates = {
        "microbe.trait.gram_stain": morphology.get("gram stain"),
        "microbe.trait.cell_shape": morphology.get("cell shape"),
        "microbe.trait.motility": morphology.get("motility"),
        "microbe.trait.spore_formation": spore.get("spore formation") or spore.get("ability"),
        "microbe.trait.oxygen_tolerance": oxygen.get("oxygen tolerance"),
        "microbe.trait.optimum_temp": _optimum(culture.get("culture temp"), "temperature"),
        "microbe.trait.optimum_ph": _optimum(culture.get("culture pH"), "pH"),
    }
    return {k: str(v) for k, v in candidates.items() if v is not None}


def _split_name(name: str) -> tuple[str, str | None]:
    """Split a scientific name into (genus, species_epithet | None) for the taxon path."""
    parts = name.strip().split()
    if not parts:
        return "", None
    genus = parts[0]
    species = parts[1] if len(parts) > 1 else None
    return genus, species


class BacdiveApiBackend(BackendBase):
    """BacDive v2 REST backend. Always configured — the v2 API is free, no key."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        max_strains_scanned: int = 1000,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._max_strains_scanned = max_strains_scanned

    def is_configured(self) -> bool:
        """The BacDive v2 API needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """BacDive v2 is a live service; the fingerprint pins the API contract version."""
        return "bacdive-api-v2"

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
        # The whole record arrives in one fetch, so we compute every trait and let
        # the shared mapper filter to requested_outputs; no per-group gating needed.
        records: list[LookupRecord] = []
        for query in queries:
            name = str(query.get("organism.scientific_name", "")).strip()
            records.append(await self._resolve_one(query, name))
        return records

    async def _resolve_one(self, query: dict[str, Any], name: str) -> LookupRecord:
        genus, species = _split_name(name)
        if not genus:
            return LookupRecord(query=query, found=False)
        try:
            type_strain = await self._find_type_strain(genus, species)
        except httpx.HTTPError as exc:  # network/HTTP problem is a per-entity error
            logger.warning("BacDive lookup failed for %r: %s", name, exc)
            return LookupRecord(query=query, error=f"BacDive API error: {exc}")

        if type_strain is None:
            return LookupRecord(query=query, found=False)
        return LookupRecord(query=query, found=True, values=_extract_traits(type_strain))

    async def _find_type_strain(self, genus: str, species: str | None) -> dict[str, Any] | None:
        """Page the taxon ID list, batch-fetch records, return the first type strain."""
        path = f"/taxon/{genus}/{species}" if species else f"/taxon/{genus}"
        scanned = 0
        while path:
            resp = await self._http().get(path)
            resp.raise_for_status()
            page = resp.json()
            ids = [int(i) for i in page.get("results", [])]
            for start in range(0, len(ids), _FETCH_BATCH):
                chunk = ids[start : start + _FETCH_BATCH]
                records = await self._fetch_records(chunk)
                for strain_id in chunk:  # preserve the taxon list's (id) order
                    record = records.get(strain_id)
                    scanned += 1
                    if record is not None and _is_type_strain(record):
                        return record
                    if scanned >= self._max_strains_scanned:
                        logger.info(
                            "scanned %d strains for %s %s without a type strain (cap reached)",
                            scanned,
                            genus,
                            species or "",
                        )
                        return None
            path = page.get("next")  # absolute URL or None; httpx handles absolute
        return None

    async def _fetch_records(self, strain_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Batch-fetch ``GET /fetch/{id1;id2;...}`` -> {strain_id: record}."""
        if not strain_ids:
            return {}
        joined = ";".join(str(i) for i in strain_ids)
        resp = await self._http().get(f"/fetch/{joined}")
        resp.raise_for_status()
        results = resp.json().get("results", {})
        return {int(k): v for k, v in results.items() if v is not None}
