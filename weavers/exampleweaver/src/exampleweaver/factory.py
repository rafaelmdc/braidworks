"""build_exampleweaver — the Layer 2 builder (only this package knows its backends)."""

from __future__ import annotations

from typing import Any

from braidworks.core import BaseWeaver

from exampleweaver.backends.local import ExampleLocalBackend
from exampleweaver.weaver import ExampleWeaver


def build_exampleweaver(**config: Any) -> BaseWeaver:
    """Construct a configured ExampleWeaver with every declared backend wired in."""
    backends = {
        "local": ExampleLocalBackend(),
    }
    return ExampleWeaver(backends)
