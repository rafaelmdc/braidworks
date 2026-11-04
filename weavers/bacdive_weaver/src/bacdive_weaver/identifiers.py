"""Conservative source identifier projection; aliases and versions are not invented."""

import re


class IdentifierEvidenceError(ValueError):
    """Malformed source evidence rather than an identifier absence."""


def collection_id(value):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*) ([A-Za-z0-9][A-Za-z0-9_.-]*)", value)
    return f"{match[1].upper()} {match[2]}" if match else None


def genome_id(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if re.fullmatch(r"GC[AF]_\d+(?:\.\d+)?", value) else None


def _rows(value):
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return value
    raise IdentifierEvidenceError("BacDive identifier evidence must contain object rows")


def project_identifiers(record):
    collections, genomes, unparsed = set(), set(), []
    for row in _rows(record.get("Literature")):
        raw = row.get("culture collection no.")
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise IdentifierEvidenceError("BacDive collection reference must be text")
        for fragment in raw.split(","):
            normalized = collection_id(fragment)
            if normalized:
                collections.add(normalized)
            else:
                unparsed.append(fragment.strip())
    for section in _rows(record.get("Sequence information")):
        for row in _rows(section.get("Genome sequences")):
            raw = row.get("INSDC accession")
            normalized = genome_id(raw)
            if normalized:
                genomes.add(normalized)
            elif raw is not None:
                unparsed.append(raw)
    return {
        "culture.collection.id": sorted(collections),
        "genome.accession": sorted(genomes),
        "microbe.bacdive.identifier_evidence": {
            "unparsed_references": unparsed,
            "policy": "observed collection tokens and exact assembly accessions; no alias or version inference",
            "source": {
                "Literature": record.get("Literature"),
                "Sequence information": record.get("Sequence information"),
            },
        },
    }
