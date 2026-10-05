"""Self-contained CLI run records; these retain observations, not source snapshots."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from braidworks.core.exceptions import BackendConfigurationError, BackendUnavailable
from braidworks.core.registry import BraidRegistry
from braidworks.core.strand import StrandSet


def begin_archive(
    inputs: list[StrandSet],
    registry: BraidRegistry,
    *,
    options: dict[str, Any],
    plans: list[dict[str, Any]],
    effective_params: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Capture inputs before execution mutates them, and declared runtime identity."""
    sources = []
    for manifest in sorted(registry.manifests(), key=lambda item: item.weaver_id):
        weaver = registry.get_weaver(manifest.weaver_id)
        fingerprints = {}
        for backend in sorted({b for cap in manifest.capabilities for b in cap.backends}):
            try:
                fingerprints[backend] = {"value": weaver.backend_fingerprint(backend)}
            except (BackendConfigurationError, BackendUnavailable, OSError) as exc:
                # Optional/unconfigured backends need not prevent a different route.
                fingerprints[backend] = {"unavailable": type(exc).__name__}
        sources.append({"manifest": manifest.to_json(), "backend_fingerprints": fingerprints})
    return {
        "schema": "braidworks.run-archive.v1",
        "started_at": datetime.now(UTC).isoformat(),
        "runtime": {
            "braidworks_core": version("braidworks-core"),
            "python": platform.python_version(),
        },
        "inputs": json.loads(json.dumps([item.to_json() for item in inputs])),
        "options": options,
        "planned_routes": plans,
        "effective_params": effective_params,
        "sources": sources,
        "limitations": [
            "Saved observations and declared fingerprints do not freeze upstream databases.",
            "This archive is not a resume checkpoint; rerunning may return different data.",
        ],
    }


def write_archive(
    path: str, archive: dict[str, Any], *, records: list[dict[str, Any]], execution: dict[str, Any]
) -> None:
    """Publish complete JSON atomically, with private permissions and no overwrite."""
    destination = Path(path)
    payload = {
        **archive,
        "finished_at": datetime.now(UTC).isoformat(),
        "records": records,
        "execution": execution,
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".braidworks-archive-",
            delete=False,
        ) as stream:
            temporary = stream.name
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            os.unlink(temporary)
