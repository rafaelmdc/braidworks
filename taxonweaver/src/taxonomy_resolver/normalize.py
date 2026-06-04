"""String normalization helpers for deterministic lookup preparation."""

from __future__ import annotations

import re

WHITESPACE_RE = re.compile(r"\s+")
VAGUE_LABEL_TOKENS = {
    "sp.",
    "spp.",
    "uncultured",
    "unclassified",
    "group",
    "cluster",
}
LEVEL_ALIASES = {
    "super kingdom": "superkingdom",
    "domain": "superkingdom",
    "kingdom": "kingdom",
    "phylum": "phylum",
    "division": "phylum",
    "class": "class",
    "order": "order",
    "family": "family",
    "genus": "genus",
    "species": "species",
}


def normalize_name(name: str) -> str:
    """Normalize a user-entered taxon string for lookup.

    This intentionally stays conservative for the deterministic layer.
    It normalizes casing and spacing without attempting typo correction,
    abbreviation expansion, or taxonomy-aware rewriting.
    """

    normalized = name.strip().lower().replace("_", " ")
    return WHITESPACE_RE.sub(" ", normalized)


def looks_vague(name: str) -> bool:
    """Flag labels that should generally route to manual review."""

    normalized = normalize_name(name)
    return any(token in normalized.split() or token in normalized for token in VAGUE_LABEL_TOKENS)


def normalize_level(level: str | None) -> str | None:
    """Normalize curator-provided taxonomic levels for soft rank comparison."""

    if level is None:
        return None
    normalized = normalize_name(level).removesuffix(" level")
    return LEVEL_ALIASES.get(normalized, normalized)
