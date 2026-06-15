"""IdmappingWeaverProvider — the Layer 1 conformance wrapper, plus registration."""

from __future__ import annotations

from typing import Any, Mapping

from braidworks.core import BaseWeaver, WeaverFactory

from idmapping_weaver import vocab
from idmapping_weaver.factory import build_idmapping_weaver


class IdmappingWeaverProvider:
    """WeaverProvider (Layer 1); delegates to build_idmapping_weaver."""

    weaver_id = vocab.WEAVER_ID

    def build(self, config: Mapping[str, Any]) -> BaseWeaver:
        return build_idmapping_weaver(**dict(config))


def register(factory: WeaverFactory) -> None:
    """Register this weaver's provider so the braider can build "idmapping"."""
    factory.register(IdmappingWeaverProvider())
