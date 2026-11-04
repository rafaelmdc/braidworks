"""Plain-language answers to "why can't I run this?".

Used by the CLI's "no route" errors and by ``braidworks doctor``. The planner reports
*what* failed ("no capability produces X"); this module explains it in the user's
terms and says what to do next: a likely typo, an input nothing installed accepts, or
a source that exists in the checkout but is not installed.

Domain-neutral: it reasons only over registered capabilities and, when run inside a
source checkout, over the ``weavers/*/weaver.spec.toml`` files next to it.
"""

from __future__ import annotations

import difflib
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from braidworks.core.registry import BraidRegistry

INSTALL_ALL = "uv sync --all-extras"


@dataclass(frozen=True)
class WorkspaceWeaver:
    """A weaver declared by a spec file in the current source checkout."""

    weaver_id: str
    package: str
    consumes: frozenset[str]
    produces: frozenset[str]


def installed_types(registry: BraidRegistry) -> tuple[set[str], set[str]]:
    """Return ``(consumed, produced)`` types across every declared capability."""
    consumed: set[str] = set()
    produced: set[str] = set()
    for manifest in registry.declared_manifests():
        for cap in manifest.capabilities:
            consumed |= cap.consumes
            produced |= cap.produces
    return consumed, produced


def backend_readiness(registry: BraidRegistry, weaver_id: str) -> tuple[list[str], list[str]]:
    """``(ready, needs_setup)`` backends for one installed weaver, across its capabilities."""
    weaver = registry.get_weaver(weaver_id)
    active = registry.get_manifest(weaver_id)
    ready: list[str] = []
    needs_setup: list[str] = []
    declared = registry.get_declared_manifest(weaver_id).capabilities
    for backend in sorted({b for cap in declared for b in cap.backends}):
        enabled = active is not None and any(backend in c.backends for c in active.capabilities)
        try:
            ok = enabled and weaver.backend_ready(backend)
        except Exception:  # noqa: BLE001 - a broken backend reads as "needs setup", never a crash
            ok = False
        (ready if ok else needs_setup).append(backend)
    return ready, needs_setup


def source_status(registry: BraidRegistry) -> list[dict]:
    """One plain record per installed source: id, version, title and backend readiness."""
    records = []
    for manifest in sorted(registry.declared_manifests(), key=lambda m: m.weaver_id):
        ready, needs_setup = backend_readiness(registry, manifest.weaver_id)
        state = "ready" if not needs_setup else ("partial" if ready else "needs_setup")
        records.append(
            {
                "source": manifest.weaver_id,
                "version": manifest.version,
                "title": manifest.title,
                "status": state,
                "ready": ready,
                "needs_setup": needs_setup,
            }
        )
    return records


def suggest_types(name: str, known: Iterable[str], limit: int = 5) -> list[str]:
    """Closest known type names: spelling matches first, then dotted-segment matches."""
    known = sorted(set(known) - {name})
    needle = name.strip().lower()
    if not needle:
        return []
    segment = [t for t in known if needle in t.lower().split(".")]
    segment.sort(key=lambda t: (len(t), t))
    spelling = difflib.get_close_matches(needle, known, n=limit, cutoff=0.75)
    return list(dict.fromkeys(spelling + segment))[:limit]


def _find_weavers_dir(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / "weavers"
        if candidate.is_dir() and any(candidate.glob("*/weaver.spec.toml")):
            return candidate
    return None


def _advertises_entry_point(pyproject: Path) -> bool:
    """True when the package is discoverable (declares a ``braidworks.weavers`` entry)."""
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return bool(data.get("project", {}).get("entry-points", {}).get("braidworks.weavers"))


def workspace_weavers(start: Path | None = None) -> list[WorkspaceWeaver]:
    """Weavers declared in the enclosing checkout; empty outside one or on bad specs."""
    weavers_dir = _find_weavers_dir((start or Path.cwd()).resolve())
    if weavers_dir is None:
        return []
    found = []
    for spec_path in sorted(weavers_dir.glob("*/weaver.spec.toml")):
        try:
            spec = tomllib.loads(spec_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        weaver_id = spec.get("weaver", {}).get("weaver_id")
        if not weaver_id or not _advertises_entry_point(spec_path.parent / "pyproject.toml"):
            continue
        consumes: set[str] = set()
        produces: set[str] = set()
        for cap in spec.get("capability", []):
            consumes.update(cap.get("consumes", []))
            produces.update(cap.get("produces", []))
            for group in cap.get("group", []):
                produces.update(group.get("outputs", []))
        found.append(
            WorkspaceWeaver(
                weaver_id=weaver_id,
                package=spec_path.parent.name.replace("_", "-"),
                consumes=frozenset(consumes),
                produces=frozenset(produces),
            )
        )
    return found


def _not_installed(registry: BraidRegistry, start: Path | None) -> list[WorkspaceWeaver]:
    installed = {m.weaver_id for m in registry.declared_manifests()}
    return [w for w in workspace_weavers(start) if w.weaver_id not in installed]


def _explain_type(
    type_name: str,
    *,
    role: str,
    known: set[str],
    missing: list[WorkspaceWeaver],
) -> list[str]:
    if role == "input":
        lines = [f"Nothing installed accepts `{type_name}` as an input."]
        providers = [w for w in missing if type_name in w.consumes]
    else:
        lines = [f"No installed source provides `{type_name}`."]
        providers = [w for w in missing if type_name in w.produces]
    if providers:
        names = ", ".join(w.weaver_id for w in providers)
        lines.append(f"  The {names} source handles it but is not installed.")
        return lines
    suggestions = suggest_types(type_name, known)
    if suggestions:
        lines.append("  Did you mean: " + ", ".join(f"`{s}`" for s in suggestions) + "?")
    else:
        lines.append("  Run `braidworks keys` to list the types installed sources use.")
    return lines


def explain_no_route(
    registry: BraidRegistry,
    have: Iterable[str],
    want: Iterable[str],
    *,
    start: Path | None = None,
) -> list[str]:
    """Human explanation and next step for a failed plan from ``have`` to ``want``."""
    consumed, produced = installed_types(registry)
    known = consumed | produced
    missing = _not_installed(registry, start)
    lines: list[str] = []
    for type_name in sorted(set(have)):
        if type_name not in consumed:
            lines += _explain_type(type_name, role="input", known=known, missing=missing)
    for type_name in sorted(set(want)):
        if type_name not in produced:
            lines += _explain_type(type_name, role="output", known=known, missing=missing)
    if any("but is not installed" in line for line in lines):
        lines.append(f"Install every source with: {INSTALL_ALL}")
    if not lines:
        have_text = ", ".join(sorted(set(have)))
        want_text = ", ".join(sorted(set(want)))
        lines.append("The installed sources cannot connect these types.")
        lines.append(f"  Inspect the gap with: braidworks path --from {have_text} --to {want_text}")
        if missing:
            lines.append(
                f"  {len(missing)} source(s) in this checkout are not installed; "
                f"{INSTALL_ALL} may add the missing link."
            )
    return lines
