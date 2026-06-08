"""BackendBase — the one operation a weaver backend adds over BackendStrategy.

A weaver's backend implements core's :class:`BackendStrategy` identity (``name`` /
``is_configured`` / ``fingerprint``) plus a batch ``fetch`` that normalizes a batch
of consumed inputs into neutral records (:mod:`braidworks.core.records`), one per
input, in input order. The :class:`BackendDispatchWeaver` calls this; core's
executor never does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BackendBase(ABC):
    """A ``BackendStrategy`` plus a batch ``fetch`` returning neutral records."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this backend is usable here (else the dispatch raises BackendUnavailable)."""

    @abstractmethod
    def fingerprint(self) -> str:
        """Per-backend data-state fingerprint for the cache key. Never ``"unknown"``."""

    @abstractmethod
    async def fetch(
        self,
        capability_id: str,
        queries: list[dict[str, Any]],
        *,
        requested_outputs: frozenset[str],
        groups_to_compute: frozenset[str],
    ) -> list[Any]:
        """Resolve consumed inputs into records — exactly one per input, in order.

        Returns :class:`~braidworks.core.records.LookupRecord` or ``ResolverRecord``
        objects (matching the weaver's mapper). ``groups_to_compute`` is the resolved
        set of triggered output-group ids (the dispatch computed it from
        ``requested_outputs``); gate expensive paths on membership in it.
        """
