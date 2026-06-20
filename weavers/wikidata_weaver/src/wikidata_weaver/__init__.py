"""wikidata_weaver — Wikidata taxon names (scientific name -> QID, vernacular names, enwiki title) weaver for Braidworks."""

from wikidata_weaver.factory import build_wikidata_weaver
from wikidata_weaver.provider import WikidataWeaverProvider, register
from wikidata_weaver.weaver import WikidataWeaver

__all__ = [
    "build_wikidata_weaver",
    "register",
    "WikidataWeaver",
    "WikidataWeaverProvider",
]
