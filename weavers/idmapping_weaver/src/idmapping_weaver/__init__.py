"""idmapping_weaver — the UniProt ID-mapping hub weaver for Braidworks.

Cross-references any supported id to/from the UniProt accession hub (gene/protein/
structure/sequence ids in; pathway/orthology/drug ids out), one typed edge per
capability, all backed by the async, batched UniProt ID-mapping REST service.
"""

from idmapping_weaver.factory import build_idmapping_weaver
from idmapping_weaver.provider import IdmappingWeaverProvider, register
from idmapping_weaver.weaver import IdmappingWeaver

__all__ = [
    "build_idmapping_weaver",
    "register",
    "IdmappingWeaver",
    "IdmappingWeaverProvider",
]
