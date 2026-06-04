"""NCBIWeaverProvider — the Layer 2 builder for the ``ncbi`` weaver.

Conforms to core's ``WeaverProvider`` so it can be registered in a ``WeaverFactory``
and assembled uniformly alongside future weavers. The actual construction logic
lives in ``build_ncbi_weaver`` (weaver-specific by nature); this is the thin
conformance wrapper.
"""

from __future__ import annotations

from typing import Any, Mapping

from braidworks.core import BaseWeaver

from . import vocab
from .factory import build_ncbi_weaver


class NCBIWeaverProvider:
    """WeaverProvider (Layer 1) for the ``ncbi`` weaver; delegates to build_ncbi_weaver."""

    weaver_id = vocab.WEAVER_ID

    def build(self, config: Mapping[str, Any]) -> BaseWeaver:
        """Build a configured NCBITaxonWeaver from a config mapping."""
        return build_ncbi_weaver(**dict(config))
