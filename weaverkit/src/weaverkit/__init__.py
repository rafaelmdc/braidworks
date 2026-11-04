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
from weaverkit.scaffold import ScaffoldError, generate_files, scaffold, validate_files, write_files
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
    "COLUMNS",
    "OUTPUT_KEYS",
    "SHARED_KEYS",
    "BulkSpec",
    "CapabilitySpec",
    "GoldenSpec",
    "GroupSpec",
    "IndexRow",
    "ScaffoldError",
    "SpecError",
    "WeaverConformanceTests",
    "WeaverSpec",
    "build_index",
    "build_rows",
    "check_fingerprints",
    "check_golden",
    "check_manifest",
    "discover_specs",
    "generate_files",
    "is_known_output",
    "is_shared_key",
    "load_spec",
    "render",
    "run_golden",
    "scaffold",
    "uncatalogued_outputs",
    "validate_files",
    "validate_spec",
    "write_files",
    "write_index",
]
