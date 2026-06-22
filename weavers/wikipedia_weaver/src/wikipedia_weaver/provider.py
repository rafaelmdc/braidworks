"""WikipediaWeaverProvider — the Layer 1 conformance wrapper, plus registration.

A weaver only becomes reachable to the braider once its provider is registered in
the application's ``WeaverFactory``. ``register(factory)`` is the one-liner that
does it; call it from wherever you assemble the factory (see the README).
"""

from __future__ import annotations

from typing import Any, Mapping

from braidworks.core import BaseWeaver, WeaverFactory

from wikipedia_weaver import vocab
from wikipedia_weaver.factory import build_wikipedia_weaver


class WikipediaWeaverProvider:
    """WeaverProvider (Layer 1); delegates to build_wikipedia_weaver."""

    weaver_id = vocab.WEAVER_ID

    def build(self, config: Mapping[str, Any]) -> BaseWeaver:
        return build_wikipedia_weaver(**dict(config))


def register(factory: WeaverFactory) -> None:
    """Register this weaver's provider so the braider can build "wikipedia"."""
    factory.register(WikipediaWeaverProvider())
