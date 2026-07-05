"""faprotax_weaver — FAPROTAX ecological function (organism lineage -> functional groups) weaver for Braidworks."""

from faprotax_weaver.factory import build_faprotax_weaver
from faprotax_weaver.provider import FaprotaxWeaverProvider, register
from faprotax_weaver.weaver import FaprotaxWeaver

__all__ = [
    "build_faprotax_weaver",
    "register",
    "FaprotaxWeaver",
    "FaprotaxWeaverProvider",
]
