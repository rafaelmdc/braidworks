"""Canonical value types for the registered shared (bridge) keys.

**Why this lives in core (a deliberate, narrow exception to domain-neutrality).**
Core stays free of domain *logic*, but the cross-weaver *vocabulary* needs one
agreed value shape per key, or the same identifier fragments: a producer emitting
``ncbi.taxon.id = 1578`` (int) and a consumer holding ``"1578"`` (str) would compute
different cache ``input_fingerprint``s and fail to join, silently. Declaring the
type contract here — and normalizing every ``Strand`` to it on construction — makes
``ncbi.taxon.id`` an ``int`` everywhere, so cache reuse and joins are consistent and
consumers no longer each re-coerce.

It must be in core (not ``weaverkit.keys``) because weavers depend on core at
runtime but only on weaverkit for tests/scaffolding — so weaverkit is not importable
when a weaver actually runs. ``weaverkit.keys.SHARED_KEYS`` (the reachability
registry) and this table are kept in lockstep by a weaverkit parity test.

This declares only the *type* of a value, never any domain behaviour.
"""

from __future__ import annotations

from typing import Any

# Registered shared key -> the canonical Python type its value takes. Scalar id-like
# keys that are numeric are ``int`` (so "1578" and 1578 collapse); free text, names,
# accessions, and ontology/EC/accession-style ids are ``str``; structured values keep
# their container type and are left untouched by ``canonicalize``.
CANONICAL_TYPES: dict[str, type] = {
    "organism.name": str,
    "ncbi.taxon.id": int,
    "organism.scientific_name": str,
    "ncbi.taxon.lineage": list,
    "ncbi.taxon.rank": str,
    "gtdb.taxon.id": str,
    "protein.uniprot.accession": str,
    "gene.ncbi.id": int,
    "gene.ensembl.id": str,
    "go.term": str,
    "enzyme.ec": str,
    "chem.chebi.id": str,
    "reaction.rhea.id": str,
    "pathway.reactome.id": str,
    "pathway.kegg.id": str,
    "protein.interpro.id": str,
    "protein.pfam.id": str,
    "pdb.id": str,
}


def canonicalize(type_id: str, value: Any) -> Any:
    """Coerce ``value`` to the canonical type declared for ``type_id``.

    Conservative and total: ``None`` stays ``None``; an unregistered ``type_id`` (a
    weaver-private type) passes through unchanged; a value that cannot be coerced is
    returned as-is (it will simply not match, rather than raising). Booleans are
    never reinterpreted as ints.
    """
    if value is None:
        return value
    target = CANONICAL_TYPES.get(type_id)
    if target is None:
        return value
    if target is int:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.lstrip("-").isdigit():
                return int(stripped)
        return value
    if target is str:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return value
    # Structured canonical types (list/dict) are left as-is.
    return value
