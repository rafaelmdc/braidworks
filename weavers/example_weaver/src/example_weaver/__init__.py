"""example_weaver — Example reference weaver (taxid -> traits, from a tiny CSV) weaver for Braidworks."""

from example_weaver.factory import build_example_weaver
from example_weaver.provider import ExampleWeaverProvider, register
from example_weaver.weaver import ExampleWeaver

__all__ = [
    "build_example_weaver",
    "register",
    "ExampleWeaver",
    "ExampleWeaverProvider",
]
