"""Source genome evidence is distinct from species-name or reference-tree placement."""

from __future__ import annotations

import math
import re
from copy import deepcopy


class GenomeFormatError(ValueError):
    """A source genome payload cannot establish a coherent identity."""


def normalize_accession(value):
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    value = value.removeprefix("RS_").removeprefix("GB_")
    return value if re.fullmatch(r"GC[AF]_\d{9}\.\d+", value) else None


def project_card(body, accession):
    if not isinstance(body, dict) or not isinstance(body.get("genome"), dict):
        raise GenomeFormatError("GTDB card requires an identified genome")
    observed = body["genome"]
    identities = {normalize_accession(observed.get(key)) for key in ("accession", "name")}
    if accession not in identities:
        raise GenomeFormatError("GTDB card genome identity mismatch")
    for field in ("metadata_gene", "metadata_nucleotide", "metadataTaxonomy"):
        if not isinstance(body.get(field), dict):
            raise GenomeFormatError(f"GTDB card requires {field}")
    for field in ("metadata_gene", "metadata_nucleotide"):
        for value in body[field].values():
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and not math.isfinite(value)
            ):
                raise GenomeFormatError("GTDB quality values must be finite")
    tax = body["metadataTaxonomy"]
    return {
        "gtdb.genome.identity": {
            "requested_accession": accession,
            "source": deepcopy(observed),
            "current_release": None,
            "scope": "observed genome card; release not supplied by endpoint",
        },
        "gtdb.genome.quality": {
            "assembly": deepcopy(body["metadata_nucleotide"]),
            "gene": deepcopy(body["metadata_gene"]),
            "ncbi": deepcopy(body.get("metadata_ncbi")),
            "interpretation": "observed genome-specific source metrics; CheckM and CheckM2 remain separate; no automatic acceptance threshold",
        },
        "gtdb.genome.synonyms": {
            "synonyms": deepcopy(tax.get("synonyms")),
            "current_taxonomy": deepcopy(tax),
            "type_material": deepcopy(body.get("metadata_type_material")),
            "interpretation": "source synonym assertions only; absent synonyms unknown, release classifications are not equivalence mappings",
        },
    }


def project_history(body, accession):
    if not isinstance(body, list):
        raise GenomeFormatError("GTDB genome history must be a list")
    by_release = {}
    for row in body:
        if not isinstance(row, dict) or not re.fullmatch(
            r"R\d+(?:\.\d+)*", str(row.get("release", ""))
        ):
            raise GenomeFormatError("GTDB history requires release-qualified records")
        if any(row.get(rank) is not None and not isinstance(row[rank], str) for rank in "dpcofgs"):
            raise GenomeFormatError("GTDB historical rank assertions must be strings or null")
        previous = by_release.setdefault(row["release"], row)
        if previous != row:
            raise GenomeFormatError("Conflicting GTDB history for one release")
    records = [
        deepcopy(by_release[key])
        for key in sorted(
            by_release, key=lambda key: tuple(int(x) for x in key[1:].split(".")), reverse=True
        )
    ]
    return {
        "requested_accession": accession,
        "records": records,
        "source": f"/genome/{accession}/taxon-history",
        "scope": "all source-returned release classifications for this genome; not a species-wide synonym or novel-genome classifier",
    }
