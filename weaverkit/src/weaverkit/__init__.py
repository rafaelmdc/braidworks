"""weaverkit — spec, scaffold, and conformance guardrails for Braidworks weavers."""

from __future__ import annotations

from weaverkit.conformance import (
    WeaverConformanceTests,
    check_fingerprints,
    check_golden,
    check_manifest,
    run_golden,
)
from weaverkit.index import (
    COLUMNS,
    IndexRow,
    build_index,
    build_rows,
    discover_specs,
    render,
    uncatalogued_outputs,
    write_index,
)
from weaverkit.keys import OUTPUT_KEYS, SHARED_KEYS, is_known_output, is_shared_key
from weaverkit.scaffold import ScaffoldError, scaffold
from weaverkit.spec import (
    BulkSpec,
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
    "OUTPUT_KEYS",
    "is_shared_key",
    "is_known_output",
    "BulkSpec",
    "CapabilitySpec",
    "GoldenSpec",
    "GroupSpec",
    "SpecError",
    "WeaverSpec",
    "load_spec",
    "validate_spec",
    "WeaverConformanceTests",
    "check_fingerprints",
    "check_golden",
    "check_manifest",
    "run_golden",
    "scaffold",
    "ScaffoldError",
    "COLUMNS",
    "IndexRow",
    "build_index",
    "build_rows",
    "discover_specs",
    "render",
    "uncatalogued_outputs",
    "write_index",
]
