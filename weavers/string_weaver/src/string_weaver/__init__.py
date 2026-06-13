"""string_weaver — STRING protein-protein interactions (accession -> partners + scores) weaver for Braidworks."""

from string_weaver.factory import build_string_weaver
from string_weaver.provider import StringWeaverProvider, register
from string_weaver.weaver import StringWeaver

__all__ = [
    "build_string_weaver",
    "register",
    "StringWeaver",
    "StringWeaverProvider",
]
