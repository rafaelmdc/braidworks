"""ExampleBackend — the domain backend interface for this weaver.

Implements core's generic ``BackendStrategy`` (``name`` / ``is_configured`` /
``fingerprint``) and adds one operation: fetch a batch of consumed inputs into
``ExampleRecord`` objects, in input order. The dispatch weaver calls this; core
never does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from exampleweaver.intermediate import ExampleRecord


class ExampleBackend(ABC):
    """A `BackendStrategy` plus a batch `fetch` operation."""

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
    ) -> list[ExampleRecord]:
        """Resolve consumed inputs into records — exactly one per input, in order."""
