"""Build an interactive HTML visualization of the weaver network and braid paths.

``weaverkit view`` discovers every installed weaver (the ``braidworks.weavers``
entry-point group), reads each one's ``MANIFEST``, and projects two things into a
single self-contained HTML file:

* **Network** — every weaver's capabilities as a ``type -> type`` graph: which
  weaver/backend owns each edge, what join keys link them, where the islands are.
* **Path** — for an optional ``from -> to`` query, the actual :class:`Braider`
  plan, laid out by dependency wave, with backends and fallbacks annotated.

It reuses the real registry and braider (no parallel reimplementation) and never
touches a weaver's plumbing — only its declared manifest. The output is one file
with no external dependencies, so it opens offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import entry_points
from pathlib import Path

from braidworks.core.braid import BackendPolicy
from braidworks.core.exceptions import NoPathError, NoPlanError
from braidworks.core.planner import Braider
from braidworks.core.registry import BraidRegistry

from weaverkit._view_template import HTML_TEMPLATE
from weaverkit.index import ENTRY_DESCRIPTION, ENTRY_KEYS
from weaverkit.keys import OUTPUT_KEYS, SHARED_KEYS

_DATA_PLACEHOLDER = "__BRAIDWORKS_DATA__"
_ENTRY_POINT_GROUP = "braidworks.weavers"


@dataclass
class Discovery:
    """The discovered registry plus any per-weaver load failures (non-fatal)."""

    registry: BraidRegistry
    problems: list[str]


def discover_registry() -> Discovery:
    """Build a registry from the ``braidworks.weavers`` entry points.

    A weaver whose zero-config builder raises is skipped with a recorded problem,
    not propagated — a partial view is more useful than no view.
    """
    registry = BraidRegistry()
    problems: list[str] = []
    for ep in entry_points(group=_ENTRY_POINT_GROUP):
        try:
            weaver = ep.load()()
            registry.register(weaver)
        except Exception as exc:  # noqa: BLE001 - one bad weaver shouldn't sink the view
            problems.append(f"{ep.name}: {type(exc).__name__}: {exc}")
    return Discovery(registry=registry, problems=problems)


# --- key classification ------------------------------------------------------


def _classify(key: str) -> tuple[str, str]:
    """Return ``(role, description)`` for a type key from the weaverkit registries."""
    if key in ENTRY_KEYS:
        return "entry", ENTRY_DESCRIPTION
    if key in SHARED_KEYS:
        return "shared", SHARED_KEYS[key]
    if key in OUTPUT_KEYS:
        return "leaf", OUTPUT_KEYS[key]
    return "uncatalogued", ""


def _short_label(key: str) -> str:
    """A compact node label: the last two dotted segments (``ncbi.taxon.id`` -> ``taxon.id``)."""
    parts = key.split(".")
    return ".".join(parts[-2:]) if len(parts) > 1 else key


def _type_node(key: str) -> dict:
    role, description = _classify(key)
    return {
        "id": f"type:{key}",
        "kind": "type",
        "key": key,
        "label": _short_label(key),
        "role": role,
        "description": description,
    }


# --- network -----------------------------------------------------------------


def build_network(registry: BraidRegistry) -> dict:
    """Project every manifest into a bipartite ``type -> weaver-op -> type`` graph.

    Each capability becomes an operation node owned by its weaver (carrying the
    weaver's color), with edges from every consumed type and to every produced
    type. Types are just endpoints; the weaver-op nodes are the actors. Unlike
    ``BraidRegistry.build_graph`` this keeps multi-input capabilities — a view
    wants the whole truth, not the planner's pruned single-input projection.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    weavers: list[dict] = []
    type_keys: set[str] = set()

    def ensure_type(key: str) -> None:
        type_keys.add(key)
        node = _type_node(key)
        nodes.setdefault(node["id"], node)

    for manifest in sorted(registry.manifests(), key=lambda m: m.weaver_id):
        backends: set[str] = set()
        cap_ids: list[str] = []
        for cap in manifest.capabilities:
            cap_ids.append(cap.id)
            backends.update(cap.backends)
            op_id = f"op:{manifest.weaver_id}:{cap.id}"
            nodes[op_id] = {
                "id": op_id,
                "kind": "op",
                "label": f"{manifest.weaver_id}\n{cap.id}",
                "weaver": manifest.weaver_id,
                "capability": cap.id,
                "backends": sorted(cap.backends),
                "input_types": sorted(cap.consumes),
                "output_types": sorted(cap.produces),
            }
            for source in sorted(cap.consumes):
                ensure_type(source)
                edges.append(
                    {"source": f"type:{source}", "target": op_id, "weaver": manifest.weaver_id}
                )
            for target in sorted(cap.produces):
                ensure_type(target)
                edges.append(
                    {"source": op_id, "target": f"type:{target}", "weaver": manifest.weaver_id}
                )
        weavers.append(
            {
                "id": manifest.weaver_id,
                "version": manifest.version,
                "backends": sorted(backends),
                "capabilities": cap_ids,
            }
        )

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "weavers": weavers,
        "stats": {
            "weavers": len(weavers),
            "types": len(type_keys),
            "edges": len(edges),
            "capabilities": sum(len(w["capabilities"]) for w in weavers),
        },
    }


# --- path --------------------------------------------------------------------

_POLICIES = {p.value: p for p in BackendPolicy}


def parse_policy(name: str) -> BackendPolicy:
    try:
        return _POLICIES[name]
    except KeyError:
        raise ValueError(
            f"unknown backend policy {name!r}; choose from {sorted(_POLICIES)}"
        ) from None


def build_path(
    registry: BraidRegistry,
    from_types: frozenset[str],
    to_types: frozenset[str],
    *,
    policy: BackendPolicy,
) -> dict:
    """Run the real braider and project the resulting plan into a layered graph.

    Type keys become pills and each step becomes an operation node, so the view
    reads as a pipeline: ``input type -> [weaver.capability] -> output type``.
    """
    braider = Braider(registry)
    braid = braider.plan(from_types, to_types, backend_policy=policy)

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def ensure_type(key: str) -> None:
        node = _type_node(key)
        nodes.setdefault(node["id"], node)

    for i, step in enumerate(braid.steps):
        op_id = f"op:{i}"
        nodes[op_id] = {
            "id": op_id,
            "kind": "op",
            "label": f"{step.weaver_id}\n{step.capability_id}",
            "weaver": step.weaver_id,
            "capability": step.capability_id,
            "primary_backend": step.primary_backend,
            "fallback_backends": list(step.fallback_backends),
            "fallback_on": sorted(c.value for c in step.fallback_on),
            "input_types": sorted(step.input_types),
            "output_types": sorted(step.output_types),
        }
        for source in sorted(step.input_types):
            ensure_type(source)
            edges.append(
                {"source": f"type:{source}", "target": op_id, "weaver": step.weaver_id}
            )
        for target in sorted(step.output_types):
            ensure_type(target)
            edges.append(
                {"source": op_id, "target": f"type:{target}", "weaver": step.weaver_id}
            )

    title = f"{', '.join(sorted(from_types))}  →  {', '.join(sorted(to_types))}"
    return {
        "title": title,
        "from_types": sorted(braid.from_types),
        "to_types": sorted(braid.to_types),
        "policy": policy.value,
        "waves": [list(w) for w in braid.waves()],
        "nodes": list(nodes.values()),
        "edges": edges,
        "step_count": len(braid.steps),
    }


# --- assembly + render -------------------------------------------------------


def build_data(
    *,
    from_types: frozenset[str] | None = None,
    to_types: frozenset[str] | None = None,
    policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
) -> dict:
    """Discover weavers and assemble the full view payload (network + optional path)."""
    discovery = discover_registry()
    registry = discovery.registry
    data: dict = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "problems": discovery.problems,
        },
        "network": build_network(registry),
        "paths": [],
    }
    if from_types and to_types:
        try:
            data["paths"].append(
                build_path(registry, from_types, to_types, policy=policy)
            )
        except (NoPathError, NoPlanError) as exc:
            data["meta"]["problems"].append(
                f"path {sorted(from_types)} -> {sorted(to_types)}: {exc}"
            )
    return data


def render_html(data: dict) -> str:
    """Inject the data payload into the self-contained HTML template."""
    return HTML_TEMPLATE.replace(_DATA_PLACEHOLDER, json.dumps(data))


def write_view(
    out_path: str | Path,
    *,
    from_types: frozenset[str] | None = None,
    to_types: frozenset[str] | None = None,
    policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
) -> dict:
    """Build the payload, render it, and write the HTML file. Returns the payload."""
    data = build_data(from_types=from_types, to_types=to_types, policy=policy)
    Path(out_path).write_text(render_html(data), encoding="utf-8")
    return data
