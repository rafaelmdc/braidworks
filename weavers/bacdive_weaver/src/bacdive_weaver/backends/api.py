"""The api backend for bacdive_weaver — BacDive (DSMZ) v2 REST API.

Strategy (MVP — type strain as the species representative):
  * ``organism.scientific_name`` is split into genus + species epithet and looked
    up via ``GET /taxon/{genus}/{species}``, which returns a paginated list of
    *strain* BacDive IDs (BacDive is strain-level; there is no species summary).
  * IDs are fetched in batches via ``GET /fetch/{id1;id2;...}`` (semicolon-joined,
    ≤100 per call), after sorting the complete distinct ID listing. The smallest
    ID flagged ``type strain == "yes"`` is the explicit representative policy.
  * That record's phenotype fields are normalized into a ``LookupRecord``.

Cost: there is no "type strains only" filter, so finding the type strain means
scanning records until the flag matches (capped by ``max_strains_scanned``). Batch
fetch keeps that cheap (e.g. E. coli's type strain is ~500 strains in → ~5 calls).
See CONTRIBUTING.md "Expansion notes" for caching and the aggregate / strain-level
modes that lift this MVP's remaining limitations.

The HTTP client is injectable (``client=``) so tests drive it with an
``httpx.MockTransport``. JSON paths were validated against real records (fetch/24,
fetch/4409); subfields are a dict for one entry, a list of dicts for many, so every
read collects all observations through ``_as_list``.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import replace
from typing import Any

import httpx
from braidworks.core import BackendBase, LookupRecord, format_exc, is_not_found_status, map_bounded
from braidworks.core.http_pacing import PacedHTTPClient
from braidworks.core.lifecycle import HTTPClientLifecycle
from braidworks.core.source_identity import remote_fingerprint

logger = logging.getLogger("bacdive_weaver.api")

DEFAULT_BASE_URL = "https://api.bacdive.dsmz.de/v2"
_FETCH_BATCH = 100  # /fetch accepts up to 100 semicolon-joined ids per call


class _InvalidResponse(ValueError):
    """A malformed BacDive source response."""


def _strain_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).isdigit():
        raise _InvalidResponse("BacDive strain identifier must be a positive integer")
    try:
        result = int(value)
    except ValueError as exc:
        raise _InvalidResponse("BacDive strain identifier is too large") from exc
    if result < 1:
        raise _InvalidResponse("BacDive strain identifier must be positive")
    return result


def _validated_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict) or "Name and taxonomic classification" not in record:
        raise _InvalidResponse("BacDive strain must contain taxonomic classification")
    for section in (
        "Name and taxonomic classification",
        "Morphology",
        "Physiology and metabolism",
        "Culture and growth conditions",
    ):
        value = record.get(section)
        if value is not None and (
            not isinstance(value, (dict, list))
            or (isinstance(value, list) and any(not isinstance(row, dict) for row in value))
        ):
            raise _InvalidResponse(f"BacDive {section} must be an object or object list")
    for section, keys in (
        ("Morphology", ("cell morphology",)),
        ("Physiology and metabolism", ("oxygen tolerance", "spore formation")),
        ("Culture and growth conditions", ("culture temp", "culture pH")),
    ):
        for section_row in _as_list(record.get(section)):
            for key in keys:
                value = section_row.get(key)
                if value is not None and (
                    not isinstance(value, (dict, list))
                    or (isinstance(value, list) and any(not isinstance(row, dict) for row in value))
                ):
                    raise _InvalidResponse(f"BacDive {key} must be an object or object list")
    return record


def _as_list(value: Any) -> list[Any]:
    """BacDive subfields are a dict for one entry, a list for many — unify to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _is_type_strain(record: dict[str, Any]) -> bool:
    flags = {
        str(row.get("type strain", "")).strip().lower()
        for row in _as_list(record.get("Name and taxonomic classification"))
    }
    if "yes" in flags and "no" in flags:
        raise _InvalidResponse("Conflicting BacDive type-strain flags require review")
    return "yes" in flags


def _canonical_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical_evidence(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return sorted(
            (_canonical_evidence(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True),
        )
    return value


def _trait_projection(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Project only agreeing observations; raw evidence retains units/references."""
    observations: dict[str, set[str]] = {}
    fields = (
        ("Morphology", "cell morphology", "gram stain", "microbe.trait.gram_stain", False),
        ("Morphology", "cell morphology", "cell shape", "microbe.trait.cell_shape", False),
        ("Morphology", "cell morphology", "motility", "microbe.trait.motility", False),
        (
            "Physiology and metabolism",
            "spore formation",
            "spore formation",
            "microbe.trait.spore_formation",
            False,
        ),
        (
            "Physiology and metabolism",
            "spore formation",
            "ability",
            "microbe.trait.spore_formation",
            False,
        ),
        (
            "Physiology and metabolism",
            "oxygen tolerance",
            "oxygen tolerance",
            "microbe.trait.oxygen_tolerance",
            False,
        ),
        (
            "Culture and growth conditions",
            "culture temp",
            "temperature",
            "microbe.trait.optimum_temp",
            True,
        ),
        ("Culture and growth conditions", "culture pH", "pH", "microbe.trait.optimum_ph", True),
    )
    for section, field, key, output, optimum in fields:
        for section_row in _as_list(record.get(section)):
            for observation in _as_list(section_row.get(field)):
                if isinstance(observation, dict) and (
                    not optimum or observation.get("type") == "optimum"
                ):
                    value = observation.get(key)
                    if value is not None:
                        observations.setdefault(output, set()).add(str(value))
    values = {
        key: next(iter(observed)) for key, observed in observations.items() if len(observed) == 1
    }
    conflicts = {
        key: sorted(observed) for key, observed in sorted(observations.items()) if len(observed) > 1
    }
    return values, conflicts


def _extract_traits(record: dict[str, Any]) -> dict[str, Any]:
    return _trait_projection(record)[0]


def _split_name(name: str) -> tuple[str, str | None]:
    """Split a scientific name into (genus, species_epithet | None) for the taxon path."""
    parts = name.strip().split()
    if not parts:
        return "", None
    genus = parts[0]
    species = parts[1] if len(parts) > 1 else None
    return genus, species


class BacdiveApiBackend(HTTPClientLifecycle, BackendBase):
    """BacDive v2 REST backend. Always configured — the v2 API is free, no key."""

    name = "api"

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        max_strains_scanned: int = 1000,
        max_concurrency: int = 4,
    ) -> None:
        self._configure_client(client, base_url)
        if (
            isinstance(max_strains_scanned, bool)
            or not isinstance(max_strains_scanned, int)
            or max_strains_scanned < 1
        ):
            raise ValueError("max_strains_scanned must be a positive integer")
        self._max_strains_scanned = max_strains_scanned
        if (
            isinstance(max_concurrency, bool)
            or not isinstance(max_concurrency, int)
            or max_concurrency < 1
        ):
            raise ValueError("max_concurrency must be a positive integer")
        self._max_concurrency = max_concurrency

    def is_configured(self) -> bool:
        """The BacDive v2 API needs no key or local data, so it's always usable."""
        return True

    def fingerprint(self) -> str:
        """BacDive v2 is a live service; the fingerprint pins the API contract version."""
        return remote_fingerprint(
            "bacdive_weaver-api",
            self._base_url,
            contract=f"bacdive-api-v2:source={self._base_url}:scan={self._max_strains_scanned}",
        )

    supports_request_pacing = True

    def _http(self) -> PacedHTTPClient:
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        return PacedHTTPClient(self._client, "bacdive", default_rate=2.0)

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
        names = [str(q.get("organism.scientific_name", "")).strip() for q in queries]
        representatives = dict(zip(names, queries))
        distinct = list(representatives)

        async def one(name):
            return await self._resolve_one(representatives[name], name)

        records = await map_bounded(distinct, one, limit=self._max_concurrency)
        by_name = dict(zip(distinct, records))
        return [
            replace(by_name[name], query=q, values=deepcopy(by_name[name].values))
            for name, q in zip(names, queries)
        ]

    async def _resolve_one(self, query: dict[str, Any], name: str) -> LookupRecord:
        genus, species = _split_name(name)
        if not genus:
            return LookupRecord(query=query, found=False)
        if len(name.split()) != 2 or species.lower() in {"sp.", "spp.", "cf.", "aff."}:
            return LookupRecord(
                query=query,
                error="BacDive type-strain lookup requires an unqualified binomial species name; genus/subspecies/strain inputs are unsupported",
            )
        try:
            type_strain = await self._find_type_strain(genus, species)
        except (
            httpx.HTTPError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            _InvalidResponse,
        ) as exc:  # expected source failures are values
            logger.warning("BacDive lookup failed for %r: %s", name, exc)
            return LookupRecord(query=query, error=f"BacDive API error: {format_exc(exc)}")

        if type_strain is None:
            return LookupRecord(query=query, found=False)
        values, conflicts = _trait_projection(type_strain)
        values["microbe.trait.records"] = {
            "scope": "type_strain_representative",
            "strain_id": type_strain["_braidworks_strain_id"],
            "matched_taxonomy": _canonical_evidence(
                type_strain["Name and taxonomic classification"]
            ),
            "conflicts": conflicts,
            "source": {
                key: _canonical_evidence(value)
                for key, value in type_strain.items()
                if key != "_braidworks_strain_id"
            },
        }
        return LookupRecord(
            query=query,
            found=True,
            values=values,
            warnings=tuple(
                f"Conflicting BacDive observations for {key}; scalar omitted: {observed}"
                for key, observed in conflicts.items()
            ),
        )

    async def _find_type_strain(self, genus: str, species: str | None) -> dict[str, Any] | None:
        """Sort the complete ID listing before bounded detail scans; smallest type ID wins."""
        path = f"/taxon/{genus}/{species}"
        seen_pages: set[str] = set()
        identifiers: set[int] = set()
        while path:
            if path in seen_pages or len(seen_pages) >= self._max_strains_scanned:
                raise _InvalidResponse(
                    "incomplete strain scan: pagination cycle/budget; complete=false"
                )
            seen_pages.add(path)
            resp = await self._http().get(path)
            if is_not_found_status(resp.status_code):
                if len(seen_pages) > 1:
                    raise _InvalidResponse("incomplete strain scan: continuation page unavailable")
                return None
            resp.raise_for_status()
            page = resp.json()
            if not isinstance(page, dict) or not isinstance(page.get("results"), list):
                raise _InvalidResponse("BacDive taxon response must contain an identifier list")
            if page.get("next") is not None and not isinstance(page["next"], str):
                raise _InvalidResponse("BacDive next page must be a URL string or null")
            identifiers.update(_strain_id(identifier) for identifier in page["results"])
            path = page.get("next")
        ids = sorted(identifiers)
        budgeted = ids[: self._max_strains_scanned]
        expected = f"{genus} {species}".casefold()
        for start in range(0, len(budgeted), _FETCH_BATCH):
            chunk = budgeted[start : start + _FETCH_BATCH]
            records = await self._fetch_records(chunk)
            for identifier in chunk:
                record = records[identifier]
                taxonomy_rows = _as_list(record["Name and taxonomic classification"])
                names = {str(row.get("species") or "").strip().casefold() for row in taxonomy_rows}
                if not names or "" in names:
                    raise _InvalidResponse("BacDive record lacks matched species identity")
                if names != {expected} or any(
                    row.get("genus") and str(row["genus"]).casefold() != genus.casefold()
                    for row in taxonomy_rows
                ):
                    raise _InvalidResponse(
                        "BacDive record species conflicts with requested binomial"
                    )
                if _is_type_strain(record):
                    return {**record, "_braidworks_strain_id": identifier}
        if len(ids) > len(budgeted):
            raise _InvalidResponse(
                f"incomplete strain scan: scanned={len(budgeted)}, limit={self._max_strains_scanned}, complete=false; type-strain absence is not established"
            )
        return None

    async def _fetch_records(self, strain_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Batch-fetch ``GET /fetch/{id1;id2;...}`` -> {strain_id: record}."""
        if not strain_ids:
            return {}
        joined = ";".join(str(i) for i in strain_ids)
        resp = await self._http().get(f"/fetch/{joined}")
        resp.raise_for_status()
        body = resp.json()
        if not isinstance(body, dict) or not isinstance(body.get("results"), dict):
            raise _InvalidResponse("BacDive fetch response must contain records keyed by strain id")
        results = {
            _strain_id(key): _validated_record(value) for key, value in body["results"].items()
        }
        if set(results) != set(strain_ids):
            raise _InvalidResponse(
                "BacDive fetch response does not match requested strain identifiers"
            )
        return results
