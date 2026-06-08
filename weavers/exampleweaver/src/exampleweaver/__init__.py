"""exampleweaver — Example reference weaver (taxid -> traits, from a tiny CSV) weaver for Braidworks."""

from exampleweaver.factory import build_exampleweaver
from exampleweaver.intermediate import ExampleRecord
from exampleweaver.provider import ExampleWeaverProvider, register
from exampleweaver.weaver import ExampleWeaver

__all__ = [
    "build_exampleweaver",
    "register",
    "ExampleRecord",
    "ExampleWeaver",
    "ExampleWeaverProvider",
]
