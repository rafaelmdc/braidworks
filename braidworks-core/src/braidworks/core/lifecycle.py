"""Optional resource ownership for asynchronous source adapters."""

from collections.abc import Iterable, Mapping
from typing import Any

import httpx

from .exceptions import BackendConfigurationError


def reject_unknown_options(options: Mapping[str, Any]) -> None:
    """Reject unused configuration without echoing potentially secret values."""
    if options:
        raise BackendConfigurationError(
            "Unsupported configuration option(s): " + ", ".join(sorted(options))
        )


class HTTPClientLifecycle:
    """Own lazy clients, borrow injected clients; closing a backend is terminal.

    Call `_configure_client` at construction and `_ensure_open` before HTTP access.
    The source adapter retains request construction and its own lazy-client defaults.
    Do not close during active requests; callers own the execution lifetime.
    """

    def _configure_client(self, client: httpx.AsyncClient | None, base_url: str) -> None:
        self._client = client
        self._owns_client = client is None
        self._closed = False
        effective = str(client.base_url) if client is not None else base_url
        try:
            url = httpx.URL(effective)
        except httpx.InvalidURL as exc:
            raise BackendConfigurationError("HTTP source requires an absolute base_url") from exc
        if url.scheme not in {"http", "https"} or not url.host:
            raise BackendConfigurationError("HTTP source requires an absolute base_url")
        if client is not None and client.is_closed:
            raise BackendConfigurationError("Injected HTTP client is already closed")
        self._base_url = effective.rstrip("/")

    def _ensure_open(self) -> None:
        if self._closed:
            raise BackendConfigurationError("HTTP backend is closed; construct a new backend")

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            if self._owns_client and self._client is not None:
                await self._client.aclose()


async def close_backends(backends: Iterable[Any]) -> None:
    """Close each distinct optional adapter once, attempting all on normal failures."""
    seen: set[int] = set()
    errors: list[Exception] = []
    for backend in backends:
        if id(backend) in seen:
            continue
        seen.add(id(backend))
        close = getattr(backend, "aclose", None)
        if close is not None:
            try:
                await close()
            except Exception as exc:  # noqa: BLE001 — cleanup attempts all independently owned adapters
                errors.append(exc)
    if errors:
        raise ExceptionGroup("Backend close failures", errors)
