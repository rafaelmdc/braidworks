"""Neutral record every backend normalizes into before the single mapper runs.

Keeping one intermediate is what guarantees every backend emits identical strand
shapes. ``values`` maps a produced ``type_id`` to its value; the mapper only emits
the externally-requested subset. This type is weaver-specific — never leak it into
``braidworks-core``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExampleRecord:
    """One backend's resolution of one input. Backend-neutral."""

    query: dict[str, Any]
    found: bool = False
    values: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
