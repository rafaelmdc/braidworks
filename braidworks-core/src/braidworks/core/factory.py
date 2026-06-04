"""The weaver factory seam — Layer 1 of the two-layer factory architecture.

Layer 2 is each weaver package's own builder (it alone knows how to turn config
into its specific backends). Layer 1, here, is the generic, domain-neutral
dispatch that maps ``weaver_id -> provider`` so an application can assemble any
weaver uniformly without hand-calling each ``build_*`` function.

This is intentionally thin. Entry-point ``discover()`` can populate the factory
later (deferred until a second weaver proves the abstraction); the
``WeaverProvider`` contract is what lets that happen without reworking weavers.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from braidworks.core.weaver import BaseWeaver


@runtime_checkable
class WeaverProvider(Protocol):
    """Layer 2 contract: a weaver package's builder.

    Domain-neutral — it says nothing about taxonomy, resolution, or backends,
    only that given config it produces a configured ``BaseWeaver``.
    """

    weaver_id: str

    def build(self, config: Mapping[str, Any]) -> BaseWeaver: ...


class WeaverFactory:
    """Layer 1: generic dispatch from ``weaver_id`` to a registered provider."""

    def __init__(self) -> None:
        self._providers: dict[str, WeaverProvider] = {}

    def register(self, provider: WeaverProvider) -> None:
        if not provider.weaver_id:
            raise ValueError("provider.weaver_id must be non-empty")
        if provider.weaver_id in self._providers:
            raise ValueError(f"provider {provider.weaver_id!r} is already registered")
        self._providers[provider.weaver_id] = provider

    def providers(self) -> tuple[str, ...]:
        return tuple(self._providers)

    def build(self, weaver_id: str, config: Mapping[str, Any]) -> BaseWeaver:
        try:
            provider = self._providers[weaver_id]
        except KeyError:
            raise KeyError(f"no weaver provider registered for {weaver_id!r}") from None
        return provider.build(config)
