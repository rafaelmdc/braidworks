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
from braidworks.core.references import references_for
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
    """Project every manifest into a ``shared-key -> weaver-op -> shared-key`` graph.

    Only **shared/bridge keys** (the join vocabulary, ``weaverkit.keys.SHARED_KEYS``,
    which includes entry keys) become type nodes — they are the connective tissue.
    Descriptive **leaf outputs** (a weaver's payload, e.g. ``pathway.reactome.names``)
    are *not* nodes; drawing them produced a "tower" of dozens of dead-end endpoints.
    They ride along on each weaver's info card instead. The result is the graph that
    actually carries meaning: which weaver bridges which keys.

    Each weaver also carries its title, provenance, capabilities, and rendered
    reference, so the view's per-weaver card needs no second pass.
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
        caps_detail: list[dict] = []
        weaver_leaves: set[str] = set()
        for cap in manifest.capabilities:
            backends.update(cap.backends)
            shared_out = sorted(k for k in cap.produces if k in SHARED_KEYS)
            leaf_out = sorted(k for k in cap.produces if k not in SHARED_KEYS)
            weaver_leaves.update(leaf_out)
            # Cardinality fan-out: produced join keys the executor can expand one→many.
            set_outputs = sorted(getattr(cap, "set_outputs", frozenset()))
            op_id = f"op:{manifest.weaver_id}:{cap.id}"
            nodes[op_id] = {
                "id": op_id,
                "kind": "op",
                "label": f"{manifest.weaver_id}\n{cap.id}",
                "weaver": manifest.weaver_id,
                "capability": cap.id,
                "backends": sorted(cap.backends),
                "input_types": sorted(cap.consumes),
                "output_types": shared_out,  # only shared keys are graph nodes
                "output_leaves": leaf_out,  # descriptive payload (card only)
                "set_outputs": set_outputs,  # one→many fan dimensions (card + edge badge)
            }
            for source in sorted(cap.consumes):
                ensure_type(source)
                edges.append(
                    {"source": f"type:{source}", "target": op_id, "weaver": manifest.weaver_id}
                )
            for target in shared_out:
                ensure_type(target)
                edges.append(
                    {
                        "source": op_id,
                        "target": f"type:{target}",
                        "weaver": manifest.weaver_id,
                        "fan": target in cap.set_outputs,  # one→many produced join key
                    }
                )
            caps_detail.append(
                {
                    "id": cap.id,
                    "consumes": sorted(cap.consumes),
                    "produces": sorted(cap.produces),
                    "backends": sorted(cap.backends),
                    "set_outputs": set_outputs,
                }
            )
        prov = manifest.provenance
        refs = references_for([manifest.weaver_id], registry)
        weavers.append(
            {
                "id": manifest.weaver_id,
                "title": manifest.title,
                "version": manifest.version,
                "backends": sorted(backends),
                "capabilities": caps_detail,
                "outputs": sorted(weaver_leaves),
                "provenance": prov.to_json() if prov is not None else None,
                "reference": refs[0].render() if refs else "",
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
        try:
            step_cap = registry.get_capability(step.weaver_id, step.capability_id)
            set_outputs = frozenset(getattr(step_cap, "set_outputs", frozenset()))
        except Exception:  # noqa: BLE001 - a missing cap shouldn't sink the path view
            set_outputs = frozenset()
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
            "set_outputs": sorted(set_outputs),
        }
        for source in sorted(step.input_types):
            ensure_type(source)
            edges.append(
                {"source": f"type:{source}", "target": op_id, "weaver": step.weaver_id}
            )
        for target in sorted(step.output_types):
            ensure_type(target)
            edges.append(
                {
                    "source": op_id,
                    "target": f"type:{target}",
                    "weaver": step.weaver_id,
                    "fan": target in set_outputs,
                }
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


# --- run lineage (cardinality fan-out trace) ---------------------------------


def _fmt_value(value: object, *, limit: int = 24) -> str:
    """Compact one-line rendering of a strand value for a node label."""
    if isinstance(value, list):
        return f"[{len(value)}]" if len(value) != 1 else _fmt_value(value[0], limit=limit)
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _leaf_value(leaf: dict, type_id: str) -> object:
    strand = leaf.get("strands", {}).get(type_id)
    return strand.get("value") if strand else None


def _result_label(leaf: dict, types: list[str], *, max_lines: int = 3) -> str:
    """A multi-line ``key=value`` label for the values a step produced on one leaf."""
    lines = [f"{_short_label(t)}={_fmt_value(_leaf_value(leaf, t))}" for t in types[:max_lines]]
    if len(types) > max_lines:
        lines.append(f"+{len(types) - max_lines} more")
    return "\n".join(lines) or "—"


def _run_graph(root: str, leaves: list[dict], cap_weaver: dict[str, str]) -> dict:
    """Project one originating input's resolved leaves into a lineage-tree graph.

    Shape: ``input → [shared ops] → fork op ─┬─ leaf value → [per-leaf ops] → …``.
    The fork is the first step whose produced value differs across the leaves (a
    cardinality fan-out); steps before it are shared, steps after it are per-leaf.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add(node_id: str, **kw) -> None:
        nodes.setdefault(node_id, {"id": node_id, **kw})

    def weaver_of(cid: str) -> str:
        return cap_weaver.get(cid) or (cid.split(".")[0] if cid else "core")

    rep = leaves[0]
    produced: set[str] = set()
    for leaf in leaves:
        for o in leaf.get("completion", []):
            produced |= set(o.get("produced", []))
    input_types = sorted(set(rep.get("strands", {})) - produced)
    input_label = ", ".join(
        f"{_short_label(t)}={_fmt_value(_leaf_value(rep, t))}" for t in input_types
    ) or root

    in_id = f"run:{root}:in"
    add(
        in_id, kind="type", key=(input_types[0] if input_types else root),
        label=input_label, role="entry",
        description=f"originating input — fanned into {len(leaves)} leaf/leaves",
    )

    # Ordered step list (first-seen cap order across the group's completions).
    steps: list[str] = []
    seen: set[str] = set()
    step_prod: dict[str, set[str]] = {}
    for leaf in leaves:
        for o in leaf.get("completion", []):
            cid = o.get("capability_id")
            if not cid or o.get("status") != "ok":
                continue
            if cid not in seen:
                seen.add(cid)
                steps.append(cid)
                step_prod[cid] = set()
            step_prod[cid] |= set(o.get("produced", []))

    def differs(cid: str) -> bool:
        return any(
            len({_fmt_value(_leaf_value(leaf, t)) for leaf in leaves}) > 1
            for t in step_prod.get(cid, ())
        )

    fork_idx = next((i for i, cid in enumerate(steps) if differs(cid)), None)
    upto = fork_idx if fork_idx is not None else len(steps)

    # Shared prefix: one op + one result node per step, chained from the input.
    prev = in_id
    for i in range(upto):
        cid = steps[i]
        ptypes = sorted(step_prod.get(cid, ()))
        op_id = f"run:{root}:op:{i}"
        add(op_id, kind="op", label=f"{weaver_of(cid)}\n{cid}", weaver=weaver_of(cid),
            capability=cid, input_types=[], output_types=ptypes)
        edges.append({"source": prev, "target": op_id, "weaver": weaver_of(cid)})
        res_id = f"run:{root}:res:{i}"
        add(res_id, kind="type", key=(ptypes[0] if ptypes else cid),
            label=_result_label(rep, ptypes), role="shared")
        edges.append({"source": op_id, "target": res_id, "weaver": weaver_of(cid)})
        prev = res_id

    title = f"Run: {input_label}"
    if fork_idx is None:
        return {"title": title, "nodes": list(nodes.values()), "edges": edges,
                "leaves": len(leaves)}

    # Fork op (shared), then a per-leaf chain for every step from the fork onward.
    title = f"Run: {input_label}  ×{len(leaves)}"
    for j in range(fork_idx, len(steps)):
        cid = steps[j]
        if j == fork_idx:
            fop_id = f"run:{root}:op:{j}"
            add(fop_id, kind="op", label=f"{weaver_of(cid)}\n{cid}", weaver=weaver_of(cid),
                capability=cid, input_types=[], output_types=sorted(step_prod.get(cid, ())),
                set_outputs=sorted(step_prod.get(cid, ())))
            edges.append({"source": prev, "target": fop_id, "weaver": weaver_of(cid)})

    for leaf in leaves:
        leaf_id = leaf.get("entity_id", root)
        branch_prev = f"run:{root}:op:{fork_idx}"
        for j in range(fork_idx, len(steps)):
            cid = steps[j]
            ptypes = sorted(step_prod.get(cid, ()))
            if j > fork_idx:
                op_id = f"run:{leaf_id}:op:{j}"
                add(op_id, kind="op", label=f"{weaver_of(cid)}\n{cid}", weaver=weaver_of(cid),
                    capability=cid, input_types=[], output_types=ptypes)
                edges.append({"source": branch_prev, "target": op_id, "weaver": weaver_of(cid)})
                branch_prev = op_id
            res_id = f"run:{leaf_id}:res:{j}"
            add(res_id, kind="type", key=(ptypes[0] if ptypes else cid),
                label=_result_label(leaf, ptypes), role="out",
                description=f"leaf {leaf_id}")
            edges.append({
                "source": branch_prev, "target": res_id, "weaver": weaver_of(cid),
                "fan": j == fork_idx,  # the fan edges fan out from the fork op
            })
            branch_prev = res_id

    return {"title": title, "nodes": list(nodes.values()), "edges": edges, "leaves": len(leaves)}


def build_run_views(
    result: dict, registry: BraidRegistry, *, max_roots: int = 16
) -> tuple[list[dict], int]:
    """Project an ``ExecutionResult.to_json()`` into per-input lineage-tree graphs.

    Returns ``(views, dropped)`` — one view per originating input (grouped by each
    resolved leaf's ``parent_id`` root), capped at ``max_roots``; ``dropped`` is how
    many roots were truncated (surfaced as a note, never silently). Only ``resolved``
    leaves are drawn — they carry the lineage; unresolved/review/error rows are summed
    into the meta by the caller.
    """
    cap_weaver: dict[str, str] = {}
    for manifest in registry.manifests():
        for cap in manifest.capabilities:
            cap_weaver[cap.id] = manifest.weaver_id

    groups: dict[str, list[dict]] = {}
    for leaf in result.get("resolved", []):
        groot = leaf.get("parent_id") or leaf.get("entity_id") or "?"
        groups.setdefault(groot, []).append(leaf)

    roots = list(groups)
    views = [_run_graph(r, groups[r], cap_weaver) for r in roots[:max_roots]]
    return views, max(0, len(roots) - max_roots)


# --- assembly + render -------------------------------------------------------


def build_data(
    *,
    from_types: frozenset[str] | None = None,
    to_types: frozenset[str] | None = None,
    policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
    run: dict | None = None,
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
        "runs": [],
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
    if run is not None:
        views, dropped = build_run_views(run, registry)
        data["runs"] = views
        if dropped:
            data["meta"]["problems"].append(
                f"run view: showing the first {len(views)} of {len(views) + dropped} "
                "originating inputs (truncated)"
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
    run: dict | None = None,
) -> dict:
    """Build the payload, render it, and write the HTML file. Returns the payload."""
    data = build_data(from_types=from_types, to_types=to_types, policy=policy, run=run)
    Path(out_path).write_text(render_html(data), encoding="utf-8")
    return data
