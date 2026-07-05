"""gtdb_weaver — GTDB genome-based taxonomy (NCBI taxid / name -> GTDB species + lineage) weaver for Braidworks."""

from gtdb_weaver.factory import build_gtdb_weaver
from gtdb_weaver.provider import GtdbWeaverProvider, register
from gtdb_weaver.weaver import GtdbWeaver

__all__ = [
    "build_gtdb_weaver",
    "register",
    "GtdbWeaver",
    "GtdbWeaverProvider",
]
