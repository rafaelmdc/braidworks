"""``weaverkit serve`` — the interactive GUI server over the live weaver network.

Where ``weaverkit view`` writes a *static* picture, ``serve`` runs a tiny localhost
server so you can **operate** the network: pick a have-type and a want-type, get the
planned braid back with the code to run it, and (Phase 2) execute it and watch the
braid light up. It is a third interface over the *same* registry / ``Braider`` /
executor — it never touches the API or CLI, and the static export is unchanged.

Design (see ``docs/gui-plan.md``): the server stays dumb. The page is served with the
network blob already injected (same as the static export), so the browser reads the
graph from that blob — there is no ``/api/network``. Only the *actions* are dynamic:

* ``POST /api/plan`` -> :func:`plan_response` — route a ``from -> to`` query and return
  the projected path plus everything derived (copyable artifacts, citations, or a
  human "why no path" message).

The request-handling logic lives in plain, FastAPI-free functions (:func:`plan_response`)
so it is unit-testable without the optional web dependency. FastAPI + uvicorn are an
**optional extra** (``pip install weaverkit[serve]``); :func:`create_app` / :func:`serve`
import them lazily and fail with a clear install hint if missing.
"""

import asyncio

from braidworks.core.braid import BackendPolicy
from braidworks.core.exceptions import NoPathError, NoPlanError
from braidworks.core.executor import ExpandPolicy, LocalExecutor
from braidworks.core.planner import Braider
from braidworks.core.references import references_for
from braidworks.core.strand import Strand, StrandSet

from weaverkit.view import (
    build_data,
    build_path,
    build_run_views,
    discover_registry,
    parse_policy,
    render_html,
)

_SERVE_EXTRA_HINT = (
    "weaverkit serve needs the optional web dependencies. "
    "Install them with:  pip install 'weaverkit[serve]'"
)


# --- request logic (FastAPI-free, unit-testable) -----------------------------


def _weave_cli_line(from_types: list[str], to_types: list[str]) -> str:
    """A copyable ``braidworks weave`` command template (values are placeholders)."""
    have = " ".join(f"--have {t}=<value>" for t in from_types)
    want = "--want " + ",".join(to_types)
    return f"braidworks weave {have} {want}".strip()


def _path_cli_line(from_types: list[str], to_types: list[str]) -> str:
    """A copyable ``braidworks path`` command (route inspection, no values needed)."""
    return f"braidworks path --from {','.join(from_types)} --to {','.join(to_types)}"


def _python_snippet(from_types: list[str], to_types: list[str]) -> str:
    """A minimal runnable Python snippet that reproduces the planned braid."""
    have = ", ".join(f'Strand("{t}", "<value>")' for t in from_types)
    want = ", ".join(repr(t) for t in to_types)
    return (
        "from braidworks.core import Braider, LocalExecutor, Strand, StrandSet\n"
        "from braidworks.core.registry import BraidRegistry\n"
        "# ... register your weavers into `registry` ...\n"
        f"braid = Braider(registry).plan(frozenset({{{', '.join(map(repr, from_types))}}}), "
        f"frozenset({{{want}}}))\n"
        f"ss = StrandSet.from_strands('e1', [{have}])\n"
        "result = await LocalExecutor(registry).execute(braid, [ss])\n"
    )


def _weaver_ids_in_path(path: dict) -> list[str]:
    """The distinct weaver ids the planned route invokes (from its op nodes)."""
    seen: list[str] = []
    for node in path.get("nodes", []):
        if node.get("kind") == "op" and node.get("weaver") and node["weaver"] not in seen:
            seen.append(node["weaver"])
    return seen


def plan_response(
    registry,
    from_types: list[str],
    to_types: list[str],
    *,
    policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
) -> dict:
    """Route ``from_types -> to_types`` and project it, with derived artifacts + citations.

    Returns ``{"ok": True, "path", "artifacts", "citations"}`` on success, or
    ``{"ok": False, "error"}`` with a human "why no path" message when unroutable.
    Pure function over the registry — no web dependency — so it is unit-testable.
    """
    frm, to = list(from_types), list(to_types)
    if not frm or not to:
        return {"ok": False, "error": "pick at least one 'have' type and one 'want' type"}
    try:
        path = build_path(registry, frozenset(frm), frozenset(to), policy=policy)
    except (NoPathError, NoPlanError) as exc:
        return {"ok": False, "error": str(exc)}

    citations = [r.render() for r in references_for(_weaver_ids_in_path(path), registry)]
    return {
        "ok": True,
        "path": path,
        "citations": citations,
        "artifacts": {
            "cli_path": _path_cli_line(frm, to),
            "cli_weave": _weave_cli_line(frm, to),
            "python": _python_snippet(frm, to),
            "braid": path,  # the projected plan is the machine-readable braid
        },
    }


def _expand_policy(mode: str, k: int) -> ExpandPolicy:
    """Map the GUI's fan-out choice onto an ``ExpandPolicy`` (top / top-k / all)."""
    if mode == "all":
        return ExpandPolicy.all()
    if mode == "top_k":
        return ExpandPolicy.top_k(max(1, k))
    return ExpandPolicy.top()


def _rows(result_json: dict) -> tuple[list[str], list[dict]]:
    """Flatten resolved strand-sets into ``(columns, rows)`` for the results table."""
    rows: list[dict] = []
    columns: list[str] = []
    for ss in result_json.get("resolved", []):
        row = {t: s.get("value") for t, s in (ss.get("strands") or {}).items()}
        for k in row:
            if k not in columns:
                columns.append(k)
        rows.append(row)
    return sorted(columns), rows


def run_response(
    registry,
    have: dict,
    want: list,
    *,
    policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
    expand: str = "top",
    k: int = 1,
) -> dict:
    """Plan ``have -> want``, **execute** it, and return results + light-up metadata.

    Returns ``{"ok": True, "path", "result", "runs", "columns", "rows", "summary"}`` —
    ``result`` is ``ExecutionResult.to_json()`` (carries the per-step ``completion`` the
    front-end replays as the light-up), ``runs`` the fan-out lineage views, ``rows`` the
    flat results table. ``{"ok": False, "error"}`` when unroutable. Pure + sync (drives the
    async executor via ``asyncio.run``), so it is unit-testable without the web dependency.
    """
    have = {str(t): v for t, v in (have or {}).items() if str(t).strip()}
    want = [str(t) for t in (want or [])]
    if not have or not want:
        return {"ok": False, "error": "enter a value for at least one Have type and a Want type"}

    braider = Braider(registry)
    try:
        braid = braider.plan(frozenset(have), frozenset(want), backend_policy=policy)
    except (NoPathError, NoPlanError) as exc:
        return {"ok": False, "error": str(exc)}

    ss = StrandSet.from_strands("e1", [Strand(t, v) for t, v in have.items()])
    executor = LocalExecutor(registry)
    result = asyncio.run(
        executor.execute(
            braid, [ss], expand_policy=_expand_policy(expand, k), backend_policy=policy
        )
    )
    rj = result.to_json()
    runs, _dropped = build_run_views(rj, registry)
    columns, rows = _rows(rj)
    return {
        "ok": True,
        "path": build_path(registry, frozenset(have), frozenset(want), policy=policy),
        "result": rj,
        "runs": runs,
        "columns": columns,
        "rows": rows,
        "summary": {
            "resolved": len(rj.get("resolved", [])),
            "unresolved": len(rj.get("unresolved", [])),
            "errors": len(rj.get("errors", [])),
        },
    }


# --- FastAPI adapter (optional; lazy import) ---------------------------------


def create_app():
    """Build the FastAPI app. Raises a clear error if the ``[serve]`` extra is missing."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
        from pydantic import BaseModel, Field
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(_SERVE_EXTRA_HINT) from exc

    # Defined here (not module level) so pydantic stays in the [serve] extra. This module
    # deliberately omits `from __future__ import annotations` so FastAPI resolves this
    # closure-local model as a request body rather than mis-reading it as query params.
    class PlanRequest(BaseModel):
        from_types: list[str] = Field(default_factory=list)
        to_types: list[str] = Field(default_factory=list)
        policy: str = "local_first"

    class RunRequest(BaseModel):
        have: dict[str, str] = Field(default_factory=dict)
        want: list[str] = Field(default_factory=list)
        policy: str = "local_first"
        expand: str = "top"  # top | top_k | all
        k: int = 3

    app = FastAPI(title="weaverkit serve", docs_url=None, redoc_url=None)

    # The page, with the network blob already injected (graph reads it; no /api/network).
    _page = render_html(build_data())

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _page

    @app.post("/api/plan")
    def api_plan(req: PlanRequest):
        registry = discover_registry().registry
        try:
            policy = parse_policy(req.policy)
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        return plan_response(registry, req.from_types, req.to_types, policy=policy)

    @app.post("/api/run")
    def api_run(req: RunRequest):
        registry = discover_registry().registry
        try:
            policy = parse_policy(req.policy)
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        return run_response(
            registry, req.have, req.want, policy=policy, expand=req.expand, k=req.k
        )

    return app


def serve(*, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Run the GUI server on localhost. Requires the ``[serve]`` extra."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(_SERVE_EXTRA_HINT) from exc

    app = create_app()
    url = f"http://{host}:{port}"
    if open_browser:
        import threading
        import webbrowser

        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    print(f"weaverkit serve — open {url}  (Ctrl-C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
