"""HTTP status classification for backend ``fetch`` error handling.

A recurring decision when wrapping a web API: which non-2xx responses mean *this
identifier simply has no data* (a routine ``NO_MATCH``) versus *the system failed*
(an error the caller must see). Across the bio APIs wrapped so far — STRING, PDBe,
AlphaFold, Reactome — an unmappable identifier comes back as **404 (not found)** or
**400 (bad/unknown identifier)**, while 5xx and network/timeout errors are real
faults. This is the shared, documented rule (build-notes #8/#17).

Kept dependency-free (no ``httpx``): a backend catches its client's
``HTTPStatusError`` itself and passes ``exc.response.status_code`` here, so core does
not take on an HTTP-client dependency.
"""

from __future__ import annotations

# 4xx codes that mean "no data for this identifier" rather than a system fault.
NOT_FOUND_STATUSES = frozenset({400, 404})


def is_not_found_status(status_code: int) -> bool:
    """True if an HTTP status means 'no data for this identifier' (a NO_MATCH).

    Everything else (notably 5xx, and any network/timeout error, which is a different
    exception type entirely) should be surfaced as a per-entity error instead.
    """
    return status_code in NOT_FOUND_STATUSES
