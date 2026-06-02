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
from typing import TYPE_CHECKING, Protocol

from braidworks.core.result import WeaveResult

if TYPE_CHECKING:
    from braidworks.core.capability import Capability
    from braidworks.core.strand import StrandSet


@dataclass(frozen=True)
class StrandCacheKey:
    """Everything that determines cache validity *except* the requested groups."""

    capability_id: str
    capability_version: str
    backend: str
    dataset_version: str
    input_fingerprint: str


def compute_cache_key(
    capability: Capability,
    strand_set: StrandSet,
    *,
    capability_version: str,
    backend: str,
    dataset_version: str,
) -> StrandCacheKey:
    """Build a cache key. The fingerprint hashes only ``capability.consumes`` values.

    Provenance is excluded (the same value via different upstream paths shares an
    entry) and extra strands in the set never affect the fingerprint.
    """
    fingerprint_inputs = {
        type_id: (s.value if (s := strand_set.get(type_id)) is not None else None)
        for type_id in capability.consumes
    }
    payload = json.dumps(fingerprint_inputs, sort_keys=True, default=str)
    input_fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return StrandCacheKey(
        capability_id=capability.id,
        capability_version=capability_version,
        backend=backend,
        dataset_version=dataset_version,
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
