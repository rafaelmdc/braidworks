"""weaverkit — spec, scaffold, and conformance guardrails for Braidworks weavers."""

from __future__ import annotations

from weaverkit.keys import SHARED_KEYS, is_shared_key
from weaverkit.spec import (
    CapabilitySpec,
    GoldenSpec,
    GroupSpec,
    SpecError,
    WeaverSpec,
    load_spec,
    validate_spec,
)

__all__ = [
    "SHARED_KEYS",
    "is_shared_key",
    "CapabilitySpec",
    "GoldenSpec",
    "GroupSpec",
    "SpecError",
    "WeaverSpec",
    "load_spec",
    "validate_spec",
]
