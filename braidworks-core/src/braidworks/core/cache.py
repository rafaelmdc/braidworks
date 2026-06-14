"""StrandCacheKey, compute_cache_key, the StrandCache protocol, and an in-memory impl.

The cache key deliberately excludes requested groups (key invariant #3). Group
validity is a *separate* superset check performed inside ``get`` (invariant #4),
so a single base key can hold several entries — one per distinct
``computed_groups`` set seen across past calls.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from braidworks.core.result import WeaveResult

if TYPE_CHECKING:
    from braidworks.core.capability import Capability
    from braidworks.core.strand import StrandSet


@dataclass(frozen=True)
class StrandCacheKey:
    """Everything that determines cache validity *except* the requested groups.

    Requested outputs and computed groups are deliberately absent — they are
    handled by the separate superset check in ``get`` (``computed_groups`` on the
    stored entry), not the key. ``backend`` and ``backend_fingerprint`` together
    keep a ``local`` result and an ``api`` result for the same input distinct.
    """

    weaver_id: str
    weaver_version: str
    capability_id: str
    backend: str
    backend_fingerprint: str
    input_fingerprint: str


def compute_cache_key(
    capability: Capability,
    strand_set: StrandSet,
    *,
    weaver_id: str,
    weaver_version: str,
    backend: str,
    backend_fingerprint: str,
    params: dict[str, Any] | None = None,
) -> StrandCacheKey:
    """Build a cache key. The fingerprint hashes ``capability.consumes`` values and
    the effective ``params``.

    Provenance is excluded (the same value via different upstream paths shares an
    entry) and extra strands in the set never affect the fingerprint. ``params`` are
    folded in so the same input under different options is a distinct entry; an empty
    ``params`` (the default) reproduces the historical key for that input.
    """
    fingerprint_inputs = {
        type_id: (s.value if (s := strand_set.get(type_id)) is not None else None)
        for type_id in capability.consumes
    }
    payload = json.dumps(
        {"in": fingerprint_inputs, "params": params or {}}, sort_keys=True, default=str
    )
    input_fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return StrandCacheKey(
        weaver_id=weaver_id,
        weaver_version=weaver_version,
        capability_id=capability.id,
        backend=backend,
        backend_fingerprint=backend_fingerprint,
        input_fingerprint=input_fingerprint,
    )


class StrandCache(Protocol):
    """Cache protocol. ``get`` takes requested_groups separately to run the
    superset scan without exposing it to callers; ``put`` indexes by
    ``result.computed_groups``."""

    def get(
        self, key: StrandCacheKey, requested_groups: frozenset[str]
    ) -> WeaveResult | None: ...

    def put(self, key: StrandCacheKey, result: WeaveResult) -> None: ...


@dataclass
class InMemoryStrandCache:
    """In-process cache: one list of results per base key, one per computed_groups set."""

    _store: dict[StrandCacheKey, list[WeaveResult]] = field(default_factory=dict)

    def get(
        self, key: StrandCacheKey, requested_groups: frozenset[str]
    ) -> WeaveResult | None:
        for entry in self._store.get(key, ()):
            if entry.computed_groups >= requested_groups:
                return entry
        return None

    def put(self, key: StrandCacheKey, result: WeaveResult) -> None:
        entries = self._store.setdefault(key, [])
        for i, entry in enumerate(entries):
            if entry.computed_groups == result.computed_groups:
                entries[i] = result  # replace the entry with matching groups
                return
        entries.append(result)
