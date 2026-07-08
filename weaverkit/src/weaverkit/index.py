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

from weaverkit.keys import OUTPUT_KEYS, SHARED_KEYS, is_known_output
from weaverkit.spec import SpecError, WeaverSpec, load_spec

SPEC_FILENAME = "weaver.spec.toml"

# Keys a user supplies directly at the start of a braid — always "met", never an
# island even if no weaver produces them.
ENTRY_KEYS: frozenset[str] = frozenset(
    {"organism.name", "protein.query", "disease.mesh.id", "disease.meddra.id", "disease.name"}
)

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
            # consumes_any: reachable if ANY one alternative is met, so it's "unmet"
            # only when none are. Conjunctive consumes need them all.
            if cap.consumes_any:
                unmet = () if any(k in met for k in cap.consumes) else tuple(cap.consumes)
            else:
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


def uncatalogued_outputs(rows: list[IndexRow]) -> list[str]:
    """Produced type_ids that are neither shared keys nor catalogued leaf outputs.

    Advisory only (Decision F): a produced field outside both registries is a
    naming-drift risk — catalog it in ``weaverkit.keys.OUTPUT_KEYS`` (or promote it
    to ``SHARED_KEYS`` if it's meant to be a join target).
    """
    produced: set[str] = set()
    for r in rows:
        produced.update(p for p in r.produces.split(";") if p)
    return sorted(p for p in produced if not is_known_output(p))


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


# --- Key-centric pivot (the human-readable companion) ------------------------
#
# The TSV above is weaver-centric (a row per capability) and machine-readable.
# The pivot below inverts it to a row per *key* — who produces it, who consumes
# it — and renders Markdown. Same data, the other axis: the TSV answers "what
# does this weaver do", the key map answers "which weavers touch this key", which
# is what you scan when wiring a new weaver in.

ENTRY_DESCRIPTION = "The text you start from — an organism name or a gene/protein query."

# role -> (Markdown section heading, lead sentence). Order here is render order.
_KEY_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("entry", "Entry", "Supplied by the user at the start of a braid."),
    ("shared", "Shared join keys", "Registered bridge keys — what links weavers together."),
    ("leaf", "Leaf outputs", "Descriptive payload fields; nothing joins on them."),
    (
        "uncatalogued",
        "Uncatalogued (naming-drift risk)",
        "Produced but in neither registry — catalog in `weaverkit.keys` to keep names stable.",
    ),
)


@dataclass(frozen=True)
class KeyRow:
    """One key's wiring across all weavers, for the human-readable key map."""

    key: str
    role: str  # entry | shared | leaf | uncatalogued
    description: str
    produced_by: str  # ";"-joined "weaver:capability"
    consumed_by: str  # ";"-joined "weaver:capability"


def _key_role(key: str) -> str:
    if key in ENTRY_KEYS:
        return "entry"
    if key in SHARED_KEYS:
        return "shared"
    if key in OUTPUT_KEYS:
        return "leaf"
    return "uncatalogued"


def _key_description(key: str, role: str) -> str:
    if role == "entry":
        return ENTRY_DESCRIPTION
    if role == "shared":
        return SHARED_KEYS[key]
    if role == "leaf":
        return OUTPUT_KEYS[key]
    return ""


def build_key_rows(rows: list[IndexRow]) -> list[KeyRow]:
    """Pivot per-capability index rows into one row per key (producers/consumers).

    The key universe is every key seen in any row's consumes/produces, unioned
    with the registries (``SHARED_KEYS`` + ``OUTPUT_KEYS`` + entry keys) — so a
    registered-but-unused key still shows (empty wiring) and an uncatalogued
    produced field surfaces.
    """
    produced_by: dict[str, list[str]] = {}
    consumed_by: dict[str, list[str]] = {}
    seen: set[str] = set()
    for row in rows:
        ref = f"{row.weaver}:{row.capability}"
        for key in (k for k in row.produces.split(";") if k):
            produced_by.setdefault(key, []).append(ref)
            seen.add(key)
        for key in (k for k in row.consumes.split(";") if k):
            consumed_by.setdefault(key, []).append(ref)
            seen.add(key)

    universe = seen | set(SHARED_KEYS) | set(OUTPUT_KEYS) | set(ENTRY_KEYS)
    key_rows: list[KeyRow] = []
    for key in sorted(universe):
        role = _key_role(key)
        key_rows.append(
            KeyRow(
                key=key,
                role=role,
                description=_key_description(key, role),
                produced_by=";".join(produced_by.get(key, [])),
                consumed_by=";".join(consumed_by.get(key, [])),
            )
        )
    return key_rows


def _md_cell(value: str) -> str:
    """Render a ``;``-joined multivalue as `code`-wrapped, comma-separated, or '—'."""
    parts = [p for p in value.split(";") if p]
    return ", ".join(f"`{p}`" for p in parts) if parts else "—"


def render_keys_md(key_rows: list[KeyRow]) -> str:
    """Render the key map as a Markdown document, sectioned by role."""
    by_role: dict[str, list[KeyRow]] = {}
    for row in key_rows:
        by_role.setdefault(row.role, []).append(row)

    lines = [
        "# Key index — what flows between weavers",
        "",
        "_Generated by `make index` (`weaverkit index`) — do not edit by hand._",
        "",
        "The inverse of [`weavers-index.tsv`](weavers-index.tsv): a row per **key**, "
        "showing which weaver produces it and which consume it. Key names and "
        "descriptions come from `weaverkit/src/weaverkit/keys.py`.",
        "",
    ]
    for role, heading, lead in _KEY_SECTIONS:
        section = by_role.get(role)
        if not section:
            continue
        lines += [f"## {heading}", "", lead, ""]
        lines += ["| Key | Description | Produced by | Consumed by |", "| --- | --- | --- | --- |"]
        for row in section:
            desc = row.description or "—"
            lines.append(
                f"| `{row.key}` | {desc} | "
                f"{_md_cell(row.produced_by)} | {_md_cell(row.consumed_by)} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_key_index(root: str | Path, out_path: str | Path) -> list[KeyRow]:
    """Build the key map from a workspace and write it as Markdown to ``out_path``."""
    out_path = Path(out_path)
    key_rows = build_key_rows(build_index(root))
    out_path.write_text(render_keys_md(key_rows), encoding="utf-8")
    return key_rows
