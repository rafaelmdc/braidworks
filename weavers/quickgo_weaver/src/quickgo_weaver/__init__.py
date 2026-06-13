"""quickgo_weaver — Gene Ontology annotations (accession -> GO terms by aspect) weaver for Braidworks."""

from quickgo_weaver.factory import build_quickgo_weaver
from quickgo_weaver.provider import QuickgoWeaverProvider, register
from quickgo_weaver.weaver import QuickgoWeaver

__all__ = [
    "build_quickgo_weaver",
    "register",
    "QuickgoWeaver",
    "QuickgoWeaverProvider",
]
