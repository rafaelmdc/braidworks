"""Build a flat index of every weaver's contract — the "what keys exist" map.

Scans a workspace for ``weaver.spec.toml`` files and emits one delimited table
(``.tsv`` / ``.csv``) with a row per capability: which weaver it belongs to, what
it consumes (inputs) and produces (outputs), its kind, backends, whether it needs
an API key, and — crucially for *linking* new weavers — which of its consumed keys
are **unmet** (no other weaver produces them, and they're not the user entry point).

This is a small index, not a database: it tells you at a glance what join keys are
already in play, so a new weaver's ``consumes`` can be picked to actually connect.
An empty ``unmet_inputs`` cell means the weaver is reachable; a non-empty one is a
hint (not an error — a weaver that only retrieves information is still useful).
"""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass
from pathlib import Path

from weaverkit.spec import SpecError, WeaverSpec, load_spec

SPEC_FILENAME = "weaver.spec.toml"

# Keys a user supplies directly at the start of a braid — always "met", never an
# island even if no weaver produces them.
ENTRY_KEYS: frozenset[str] = frozenset({"organism.name"})

# Directory names skipped during discovery (test fixtures aren't real weavers).
_SKIP_DIRS: frozenset[str] = frozenset({"tests", "fixtures", "build", "dist", "__pycache__"})

COLUMNS: tuple[str, ...] = (
    "weaver",
    "capability",
    "kind",
    "api_key",
    "backends",
    "consumes",
    "produces",
    "unmet_inputs",
)


@dataclass(frozen=True)
class IndexRow:
    """One capability's contract, flattened for the index table."""

    weaver: str
    capability: str
    kind: str
    api_key: str
    backends: str
    consumes: str
    produces: str
    unmet_inputs: str


def discover_specs(root: str | Path) -> list[Path]:
    """Find every real ``weaver.spec.toml`` under ``root`` (skipping test fixtures)."""
    root = Path(root)
    found: list[Path] = []
    for path in sorted(root.rglob(SPEC_FILENAME)):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        found.append(path)
    return found


def build_rows(specs: list[WeaverSpec]) -> list[IndexRow]:
    """Flatten loaded specs into index rows, computing cross-weaver reachability."""
    produced: set[str] = set()
    for spec in specs:
        for cap in spec.capabilities:
            produced.update(cap.produces)
    met = produced | ENTRY_KEYS

    rows: list[IndexRow] = []
    for spec in sorted(specs, key=lambda s: s.resolved_weaver_id):
        for cap in spec.capabilities:
            unmet = tuple(k for k in cap.consumes if k not in met)
            rows.append(
                IndexRow(
                    weaver=spec.resolved_weaver_id,
                    capability=cap.id,
                    kind=spec.kind,
                    api_key=spec.api_key,
                    backends=";".join(spec.backends),
                    consumes=";".join(cap.consumes),
                    produces=";".join(cap.produces),
                    unmet_inputs=";".join(unmet),
                )
            )
    return rows


def render(rows: list[IndexRow], *, delimiter: str = "\t") -> str:
    """Render rows as a delimited table with a header line."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, delimiter=delimiter, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(asdict(row))
    return buf.getvalue()


def _delimiter_for(out_path: Path) -> str:
    return "," if out_path.suffix.lower() == ".csv" else "\t"


def build_index(root: str | Path) -> list[IndexRow]:
    """Discover + load + flatten every weaver under ``root`` into index rows.

    Skips spec files that fail to load (returns what it can) — the index is a map,
    not a gate; ``weaverkit verify`` is where a malformed spec should fail.
    """
    specs: list[WeaverSpec] = []
    for path in discover_specs(root):
        try:
            specs.append(load_spec(path))
        except SpecError:
            continue
    return build_rows(specs)


def write_index(root: str | Path, out_path: str | Path) -> list[IndexRow]:
    """Build the index and write it to ``out_path`` (delimiter from its suffix)."""
    out_path = Path(out_path)
    rows = build_index(root)
    out_path.write_text(render(rows, delimiter=_delimiter_for(out_path)), encoding="utf-8")
    return rows
