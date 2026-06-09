"""build_example_weaver — the Layer 2 builder (only this package knows its backends)."""

from __future__ import annotations

from typing import Any

from braidworks.core import BaseWeaver

from example_weaver.backends.local import ExampleLocalBackend
from example_weaver.weaver import ExampleWeaver


def build_example_weaver(**config: Any) -> BaseWeaver:
    """Construct a configured ExampleWeaver with every declared backend wired in."""
    backends = {
        "local": ExampleLocalBackend(),
    }
    return ExampleWeaver(backends)
