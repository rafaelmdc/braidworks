"""Exact primary-accession description: pure projections and bounded bulk acquisition."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from re import Pattern
from typing import Any

import httpx
from braidworks.core import LookupRecord, format_exc, is_not_found_status
from braidworks.core.http_pacing import PacedHTTPClient

from uniprot_weaver.backends.jobs import _next_link
from uniprot_weaver.backends.validation import _InvalidResponse, _object, _rows

SEQUENCE = "protein.sequence"
ANNOTATIONS = "protein.annotation.records"
_CHUNK = 25
_MAX_PAGES = 10


def _validate_evidence(value: Any) -> None:
    """Retain arbitrary source fields but validate evidence envelopes recursively."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "evidences":
                for evidence in _rows(child, "evidences"):
                    code = evidence.get("evidenceCode")
                    if not isinstance(code, str) or not code:
                        raise _InvalidResponse("UniProt evidence must contain evidenceCode")
                    for field in ("source", "id"):
                        if evidence.get(field) is not None and not isinstance(evidence[field], str):
                            raise _InvalidResponse(f"UniProt evidence {field} must be a string")
            _validate_evidence(child)
    elif isinstance(value, list):
        for child in value:
            _validate_evidence(child)


def annotation_records(entry: dict[str, Any], release: dict[str, str]) -> dict[str, Any]:
    """Preserve source evidence and coordinates without flattening or inventing them."""
    records: dict[str, Any] = {}
    for field in ("comments", "features", "references"):
        records[field] = deepcopy(_rows(entry.get(field, []), field))
    for feature in records["features"]:
        if not isinstance(feature.get("type"), str) or not feature["type"]:
            raise _InvalidResponse("UniProt feature must contain type")
        if feature.get("location") is not None:
            _object(feature["location"], "feature location")
    for reference in records["references"]:
        if reference.get("citation") is not None:
            _object(reference["citation"], "reference citation")
    if entry.get("entryAudit") is not None:
        records["entryAudit"] = deepcopy(_object(entry["entryAudit"], "entryAudit"))
    if entry.get("proteinExistence") is not None:
        if not isinstance(entry["proteinExistence"], str):
            raise _InvalidResponse("UniProt proteinExistence must be a string")
        records["proteinExistence"] = entry["proteinExistence"]
    records["release"] = dict(release)
    _validate_evidence(records)
    # Reject non-JSON numerical tokens, including NaN accepted by Python's decoder.
    try:
        json.dumps(records, allow_nan=False)
    except ValueError as exc:
        raise _InvalidResponse("UniProt annotation contains a non-finite value") from exc
    return records


def describe_values(
    entry: dict[str, Any],
    groups: frozenset[str],
    release: dict[str, str],
    *,
    identity: dict[str, Any],
) -> dict[str, Any]:
    """Pure group projection; identity is normalized by the existing source mapper."""
    values = dict(identity)
    if "sequence" in groups:
        sequence = _object(entry.get("sequence"), "sequence")
        value = sequence.get("value")
        if not isinstance(value, str) or not value or not value.isascii() or not value.isalpha():
            raise _InvalidResponse(
                "UniProt canonical sequence must be a nonempty amino-acid string"
            )
        if sequence.get("length") != len(value):
            raise _InvalidResponse("UniProt canonical sequence length disagrees with sequence")
        values[SEQUENCE] = value
    if "annotations" in groups:
        values[ANNOTATIONS] = annotation_records(entry, release)
    return values


async def describe_batch(
    http: PacedHTTPClient,
    queries: list[dict[str, Any]],
    *,
    groups: frozenset[str],
    fields: str,
    accession_pattern: Pattern[str],
    validate_entry: Callable[[dict[str, Any]], None],
    extract_identity: Callable[[dict[str, Any]], dict[str, Any]],
) -> list[LookupRecord]:
    """Bulk exact accessions; source failures discard only their entire chunk."""
    key = "protein.uniprot.accession"
    accessions = [str(query.get(key) or "").strip().upper() for query in queries]
    ids = sorted({acc for acc in accessions if accession_pattern.fullmatch(acc)})
    resolved: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for offset in range(0, len(ids), _CHUNK):
        chunk = ids[offset : offset + _CHUNK]
        try:
            url: str | None = "/uniprotkb/search"
            params: dict[str, Any] | None = {
                "query": " OR ".join(f"accession:{acc}" for acc in chunk),
                "format": "json",
                "size": "500",
            }
            if "annotations" not in groups:
                params["fields"] = fields + (",sequence" if "sequence" in groups else "")
            visited: set[str] = set()
            entries: dict[str, dict[str, Any]] = {}
            entry_errors: dict[str, str] = {}
            while url:
                if url in visited or len(visited) >= _MAX_PAGES:
                    raise _InvalidResponse(
                        "UniProt description pagination repeats or exceeds budget"
                    )
                visited.add(url)
                response = await http.get(url, params=params)
                if is_not_found_status(response.status_code):
                    if len(visited) > 1:
                        raise _InvalidResponse("UniProt description continuation is unavailable")
                    break
                response.raise_for_status()
                body = _object(response.json(), "description response")
                release = {
                    k: response.headers[h]
                    for k, h in (
                        ("version", "x-uniprot-release"),
                        ("date", "x-uniprot-release-date"),
                    )
                    if h in response.headers
                }
                for entry in _rows(body.get("results"), "description results"):
                    acc = entry.get("primaryAccession")
                    if not isinstance(acc, str) or not acc:
                        raise _InvalidResponse("UniProt description has no primaryAccession")
                    # Secondary accession search hits must not substitute a different identity.
                    if acc not in chunk:
                        continue
                    if acc in entries or acc in entry_errors:
                        raise _InvalidResponse("UniProt description repeats a primary accession")
                    try:
                        validate_entry(entry)
                        entries[acc] = describe_values(
                            entry, groups, release, identity=extract_identity(entry)
                        )
                    except _InvalidResponse as exc:
                        entry_errors[acc] = f"UniProt description error: {format_exc(exc)}"
                url = _next_link(response)
                if url is not None:
                    try:
                        next_url = response.url.join(url)
                    except httpx.InvalidURL as exc:
                        raise _InvalidResponse(
                            "UniProt description continuation URL is invalid"
                        ) from exc
                    if next_url.scheme not in {"http", "https"} or not next_url.host:
                        raise _InvalidResponse("UniProt description continuation must use HTTP(S)")
                    url = str(next_url)
                params = None
            resolved.update(entries)
            errors.update(entry_errors)
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError, _InvalidResponse) as exc:
            error = f"UniProt description error: {format_exc(exc)}"
            errors.update({acc: error for acc in chunk})
    return [
        LookupRecord(query=query, error=errors[acc])
        if acc in errors
        else LookupRecord(query=query, found=True, values=deepcopy(resolved[acc]))
        if acc in resolved
        else LookupRecord(query=query, found=False)
        for query, acc in zip(queries, accessions, strict=True)
    ]
