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
import io

from braidworks.core.braid import BackendPolicy
from braidworks.core.exceptions import BraidworksError, NoPathError, NoPlanError
from braidworks.core.executor import (
    ExecutionResult,
    ExpandPolicy,
    LocalExecutor,
    ReviewPolicy,
)
from braidworks.core.inputs import read_input_rows
from braidworks.core.outcomes import execution_records
from braidworks.core.parameters import validate_scoped_parameters
from braidworks.core.planner import Braider
from braidworks.core.query import (
    QueryOptions,
    QueryRequest,
    execute_query,
    normalize_expansion,
    prepare_query,
)
from braidworks.core.references import references_for
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.traverse import resolve_traversal, traversal_route_capabilities

from weaverkit.codegen import cli_artifact, path_artifact, python_artifact
from weaverkit.view import (
    build_data,
    build_path,
    build_run_views,
    discover_registry,
    parse_policy,
    render_html,
    render_path,
)

_SERVE_EXTRA_HINT = (
    "weaverkit serve needs the optional web dependencies. "
    "Install them with:  pip install 'weaverkit[serve]'"
)


# --- request logic (FastAPI-free, unit-testable) -----------------------------


def _prepare_experiment(registry, have, want, traverse, batch=None, **options):
    sets = (
        batch_inputs(have, batch)
        if batch is not None
        else [StrandSet.from_strands("e1", [Strand(key, value) for key, value in have.items()])]
    )
    if not sets[0].available_types() or (not want and not traverse):
        raise ValueError("choose inputs and outputs or a pass-through step")
    for i, ss in enumerate(sets, 1):
        ss.source_row = i
    return prepare_query(
        registry,
        QueryRequest(
            tuple(sets),
            frozenset(want),
            tuple(traverse or ()),
            options.get("params") or {},
            QueryOptions(
                options.get("policy", BackendPolicy.LOCAL_FIRST),
                normalize_expansion(options.get("expand", "top"), options.get("k", 1)),
                ReviewPolicy(options.get("review_policy", "halt")),
                options.get("confidence_threshold", 0.0),
                options.get("max_expansion", 10_000),
            ),
        ),
    )


def code_response(
    registry,
    have,
    want,
    traverse=None,
    *,
    policy=BackendPolicy.LOCAL_FIRST,
    expand="top",
    k=1,
    params=None,
    max_expansion=10_000,
    review_policy="halt",
    confidence_threshold=0.0,
    _prepared=None,
):
    """Render validated query artifacts without repeating planning or execution."""
    options = {
        "policy": policy,
        "expand": expand,
        "k": k,
        "params": params,
        "max_expansion": max_expansion,
        "review_policy": review_policy,
        "confidence_threshold": confidence_threshold,
    }
    return _code_response(registry, have, want, traverse, None, options, _prepared)


def _code_response(registry, have, want, traverse, batch, options, prepared=None):
    try:
        prepared = prepared or _prepare_experiment(registry, have, want, traverse, batch, **options)
        settings = prepared.request.options
        path = (
            render_path(registry, prepared.plans[0][0], policy=settings.backend_policy)
            if (batch is None and prepared.plans and not prepared.traversals)
            else None
        )
        recipe = {
            "have": have,
            "want": want,
            "traverse": traverse or [],
            "policy": settings.backend_policy.value,
            "expand": settings.expand_policy.mode.value,
            "k": settings.expand_policy.k,
            "max_expansion": settings.max_expansion,
            "params": prepared.effective_params,
            "review_policy": settings.review_policy.value,
            "confidence_threshold": settings.confidence_threshold,
            "path": path,
        }
        if batch is not None:
            recipe.update(
                batch=batch, planned_routes=[braid.to_json() for braid, _ in prepared.plans]
            )
        return {
            "ok": True,
            "effective_params": _prepared_effective(registry, prepared),
            "artifacts": {
                "cli_weave": cli_artifact(prepared, have, batch=batch),
                "cli_path": path_artifact(prepared, have, batch=batch),
                "python": python_artifact(prepared),
                "braid": recipe,
            },
        }
    except (ValueError, BraidworksError) as exc:
        return {"ok": False, "error": str(exc)}


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
    traverse: list[str] | None = None,
) -> dict:
    """Preview routes and expose refinements without running any source."""
    frm, to = list(from_types), list(to_types)
    if not frm or (not to and not traverse):
        return {"ok": False, "error": "pick at least one Have type and a Want or pass-through step"}
    try:
        if traverse:
            traversals = [resolve_traversal(registry, token) for token in traverse]
            inputs = [StrandSet.from_strands("preview", [Strand(key, None) for key in frm])]
            caps = traversal_route_capabilities(
                registry, inputs, traversals, frozenset(to), backend_policy=policy
            )
            return {
                "ok": True,
                "path": None,
                "traverse": [cid for _, cid in traversals],
                "parameter_capabilities": _parameter_capabilities(registry, caps),
                "citations": [],
                "artifacts": {},
            }
        prepared = _prepare_experiment(
            registry, {key: "<value>" for key in frm}, to, [], policy=policy
        )
        path = render_path(registry, prepared.plans[0][0], policy=policy)
    except (NoPathError, NoPlanError) as exc:
        return {"ok": False, "error": str(exc)}
    artifacts = code_response(
        registry, {key: "<value>" for key in frm}, to, policy=policy, _prepared=prepared
    )["artifacts"]
    return {
        "ok": True,
        "path": path,
        "parameter_capabilities": _parameter_capabilities(
            registry, _path_capabilities(registry, path)
        ),
        "citations": [ref.render() for ref in references_for(_weaver_ids_in_path(path), registry)],
        "artifacts": {**artifacts, "braid": path},
    }


def _path_capabilities(registry, path):
    return {
        node["capability"]: registry.get_capability(node["weaver"], node["capability"])
        for node in path.get("nodes", [])
        if node.get("kind") == "op"
    }


def _parameter_capabilities(registry, caps):
    owners = {
        cap.id: manifest.weaver_id
        for manifest in registry.manifests()
        for cap in manifest.capabilities
    }
    return [
        {
            "weaver": owners[cid],
            "capability": cid,
            "parameters": [parameter.to_json() for parameter in cap.parameters],
        }
        for cid, cap in caps.items()
        if cap.parameters
    ]


def _effective_parameters(params, caps):
    if not isinstance(params or {}, dict) or any(
        not isinstance(value, dict) for value in (params or {}).values()
    ):
        raise ValueError("params must map capability IDs to parameter objects")
    validated = validate_scoped_parameters(params or {}, caps)
    display = {
        cid: {p.name: cap.resolve_params(validated.get(cid)).get(p.name) for p in cap.parameters}
        for cid, cap in caps.items()
        if cap.parameters
    }
    return validated, display


def _prepared_effective(registry, prepared):
    return {
        cid: {p.name: prepared.effective_params[cid].get(p.name) for p in cap.parameters}
        for wid, cid in prepared.capability_ids
        if (cap := registry.get_capability(wid, cid)).parameters
    }


def _expand_policy(mode: str, k: int) -> ExpandPolicy:
    """Map the GUI's fan-out choice onto an ``ExpandPolicy`` (top / top-k / all)."""
    if mode == "all":
        return ExpandPolicy.all()
    if mode == "top_k":
        return ExpandPolicy.top_k(max(1, k))
    return ExpandPolicy.top()


def _rows(result_json: dict, want: list | None = None) -> tuple[list[str], list[dict]]:
    """Flatten shared terminal records while retaining identity and diagnostics."""
    rows: list[dict] = []
    columns: list[str] = []
    for record in execution_records(ExecutionResult.from_json(result_json), []):
        record["missing"] = [target for target in want or [] if target not in record["values"]]
        row = {key: value for key, value in record.items() if key != "values"}
        row.update(record["values"])
        for k in row:
            if k not in columns:
                columns.append(k)
        rows.append(row)
    identity = [
        key
        for key in ("entity", "parent", "status", "source_row", "outcome", "missing")
        if key in columns
    ]
    return identity + sorted(set(columns) - set(identity)), rows


def _error_list(result_json: dict) -> list[dict]:
    """Flatten the errors bucket into compact rows the GUI can show (message + context)."""
    out: list[dict] = []
    for e in result_json.get("errors", []):
        out.append(
            {
                "entity": (e.get("strand_set") or {}).get("entity_id"),
                "type": e.get("error_type"),
                "category": e.get("category"),
                "capability": e.get("capability_id"),
                "message": e.get("message"),
            }
        )
    return out


def batch_code_response(registry, have, want, traverse, batch, **options):
    """Render the entire normalized batch through the same core query service."""
    return _code_response(registry, have, want, traverse, batch, options)


def batch_inputs(have, batch):
    fmt = batch.get("format", "lines")
    if fmt not in {"lines", "csv", "tsv"}:
        raise ValueError("batch format must be lines, csv or tsv")
    input_type = batch.get("input_type") if fmt == "lines" else None
    if fmt == "lines" and not input_type:
        raise ValueError("choose a type for one-value-per-line inputs")
    rows = read_input_rows(
        io.StringIO(batch.get("text", "")),
        input_type=input_type,
        delimiter="," if fmt == "csv" else "\t",
    )
    if not rows:
        raise ValueError("batch contains no input rows")
    sets = []
    for i, row in enumerate(rows, 1):
        ss = StrandSet.from_strands(
            row[input_type] if input_type else f"e{i}",
            [Strand(key, value) for key, value in {**have, **row}.items()],
        )
        ss.source_row = i
        sets.append(ss)
    return sets


async def execute_batch_response(
    registry,
    have,
    want,
    traverse,
    batch,
    *,
    policy=BackendPolicy.LOCAL_FIRST,
    expand="top",
    k=1,
    params=None,
    max_expansion=10_000,
    review_policy="halt",
    confidence_threshold=0.0,
    on_event=None,
):
    """Plan every row group before I/O, then execute with one shared expansion budget."""
    prepared = _prepare_experiment(
        registry,
        have,
        want,
        traverse,
        batch,
        policy=policy,
        expand=expand,
        k=k,
        params=params,
        max_expansion=max_expansion,
        review_policy=review_policy,
        confidence_threshold=confidence_threshold,
    )
    sets = list(prepared.request.inputs)
    result = await execute_query(registry, prepared, on_event=on_event)
    traversals = prepared.traversals
    plans = [(braid, [sets[i] for i in indices]) for braid, indices in prepared.plans]
    effective = _prepared_effective(registry, prepared)
    payload = _traverse_payload(registry, result, want, [cid for _, cid in traversals])
    if len(plans) == 1:
        payload["path"] = render_path(registry, plans[0][0], policy=policy)
    payload["summary"]["inputs"] = len(sets)
    return {
        **payload,
        "effective_params": effective,
        "planned_routes": [braid.to_json() for braid, _ in plans],
        "review_policy": review_policy,
        "confidence_threshold": confidence_threshold,
    }


def _clean_run_inputs(have: dict, want: list) -> tuple[dict, list, str | None]:
    """Normalize have/want; return ``(have, want, error)`` (error set if either is empty)."""
    have = {str(t): v for t, v in (have or {}).items() if str(t).strip()}
    want = [str(t) for t in (want or [])]
    if not have or not want:
        return have, want, "enter a value for at least one Have type and a Want type"
    return have, want, None


def _run_payload(
    registry, result, have: dict, want: list, *, policy: BackendPolicy, braid=None
) -> dict:
    """Assemble the run response from an ``ExecutionResult`` (shared by sync + streaming)."""
    rj = result.to_json()
    runs, _dropped = build_run_views(rj, registry)
    columns, rows = _rows(rj, want)
    return {
        "ok": True,
        "path": render_path(registry, braid, policy=policy)
        if braid is not None
        else build_path(registry, frozenset(have), frozenset(want), policy=policy),
        "result": rj,
        "runs": runs,
        "columns": columns,
        "identity_columns": _identity_columns(registry, columns),
        "rows": rows,
        "want": list(want),  # the requested targets — GUI defaults the table to these
        "errors": _error_list(rj),
        "summary": {
            "resolved": len(rj.get("resolved", [])),
            "unresolved": len(rj.get("unresolved", [])),
            "review": len(rj.get("review_queue", [])),
            "total": result.total(),
            "truncated_forks": len(result.truncations),
            "errors": len(rj.get("errors", [])),
        },
    }


def run_response(
    registry,
    have: dict,
    want: list,
    *,
    policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
    expand: str = "top",
    k: int = 1,
    params: dict | None = None,
    max_expansion: int = 10_000,
    review_policy: str = "halt",
    confidence_threshold: float = 0.0,
) -> dict:
    """Plan ``have -> want``, **execute** it, and return results + light-up metadata.

    Returns ``{"ok": True, "path", "result", "runs", "columns", "rows", "summary"}`` —
    ``result`` is ``ExecutionResult.to_json()`` (carries the per-step ``completion`` the
    front-end replays as the light-up), ``runs`` the fan-out lineage views, ``rows`` the
    flat results table. ``{"ok": False, "error"}`` when unroutable. Pure + sync (drives the
    async executor via ``asyncio.run``), so it is unit-testable without the web dependency.
    """
    have, want, err = _clean_run_inputs(have, want)
    if err:
        return {"ok": False, "error": err}
    ss = StrandSet.from_strands("e1", [Strand(t, v) for t, v in have.items()])
    ss.source_row = 1
    try:
        prepared = prepare_query(
            registry,
            QueryRequest(
                (ss,),
                frozenset(want),
                params=params or {},
                options=QueryOptions(
                    policy,
                    normalize_expansion(expand, k),
                    ReviewPolicy(review_policy),
                    confidence_threshold,
                    max_expansion,
                ),
            ),
        )
        result = asyncio.run(execute_query(registry, prepared))
        effective = _prepared_effective(registry, prepared)
    except (ValueError, BraidworksError) as exc:
        return {"ok": False, "error": str(exc)}
    return {
        **_run_payload(registry, result, have, want, policy=policy, braid=prepared.plans[0][0]),
        "effective_params": effective,
        "review_policy": review_policy,
        "confidence_threshold": confidence_threshold,
    }


def run_traversed_response(
    registry,
    have: dict,
    want: list,
    traverse: list,
    *,
    policy: BackendPolicy = BackendPolicy.LOCAL_FIRST,
    expand: str = "all",
    k: int = 5,
    params: dict | None = None,
    max_expansion: int = 10_000,
    review_policy: str = "halt",
    confidence_threshold: float = 0.0,
) -> dict:
    """Fan *through* one or more relationships (the GUI's "pass through" = --for-each).

    ``traverse`` is a list of fan capability tokens (relationship noun or capability id,
    e.g. ``ncbi.list_orthologs``). Each is run in order, re-rooting on every produced
    value, then ``want`` is planned from each child (``want`` may be empty — you just get
    the fanned entities). Returns the same shape as :func:`run_response` minus ``path``
    (a traversal is not a single Dijkstra route, so there is no one route view).
    """
    have = {str(t): v for t, v in (have or {}).items() if str(t).strip()}
    want = [str(t) for t in (want or [])]
    tokens = [str(t) for t in (traverse or []) if str(t).strip()]
    if not have or not tokens:
        return {"ok": False, "error": "pass-through needs a Have value and at least one step"}
    try:
        return asyncio.run(
            execute_batch_response(
                registry,
                have,
                want,
                tokens,
                None,
                policy=policy,
                expand=expand,
                k=k,
                params=params,
                max_expansion=max_expansion,
                review_policy=review_policy,
                confidence_threshold=confidence_threshold,
            )
        )
    except (ValueError, BraidworksError) as exc:
        return {"ok": False, "error": str(exc)}


def _traverse_payload(registry, result, want: list, traverse_ids: list) -> dict:
    """Shape a traversal ExecutionResult like run_response (no single ``path``)."""
    rj = result.to_json()
    runs, _dropped = build_run_views(rj, registry)
    columns, rows = _rows(rj, want)
    return {
        "ok": True,
        "path": None,  # a traversal is not a single route; the results table is the payload
        "result": rj,
        "runs": runs,
        "columns": columns,
        "identity_columns": _identity_columns(registry, columns),
        "rows": rows,
        "want": list(want),
        "traverse": traverse_ids,
        "errors": _error_list(rj),
        "summary": {
            "resolved": len(rj.get("resolved", [])),
            "unresolved": len(rj.get("unresolved", [])),
            "review": len(rj.get("review_queue", [])),
            "total": result.total(),
            "truncated_forks": len(result.truncations),
            "errors": len(rj.get("errors", [])),
        },
    }


def _identity_columns(registry, columns):
    keys = {
        key
        for manifest in registry.manifests()
        for cap in manifest.capabilities
        for key in cap.set_outputs
    }
    return [
        column
        for column in columns
        if column in keys
        or column
        in {"entity", "parent", "status", "source_row", "outcome", "missing", "requires_review"}
    ]


# --- FastAPI adapter (optional; lazy import) ---------------------------------


def create_app():
    """Build the FastAPI app. Raises a clear error if the ``[serve]`` extra is missing."""
    import asyncio as _asyncio
    import json as _json

    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
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
        traverse: list[str] = Field(default_factory=list)

    class BatchInput(BaseModel):
        text: str
        format: str = "lines"
        input_type: str | None = None

    class RunRequest(BaseModel):
        batch: BatchInput | None = None
        have: dict[str, str] = Field(default_factory=dict)
        want: list[str] = Field(default_factory=list)
        policy: str = "local_first"
        expand: str = "top"  # top | top_k | all
        k: int = 3
        traverse: list[str] = Field(default_factory=list)  # fan capabilities to pass through
        params: dict[str, dict[str, str]] = Field(default_factory=dict)  # {cap_id: {name: value}}
        max_expansion: int = Field(default=10_000, ge=1)
        review_policy: str = "halt"
        confidence_threshold: float = Field(default=0.0, ge=0.0, le=1.0)

    app = FastAPI(title="weaverkit serve", docs_url=None, redoc_url=None)

    # The page, with the network blob injected (graph reads it; no /api/network) and the
    # interactive builder/run/results UI slotted in (interactive=True).
    _page = render_html(build_data(), interactive=True)

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
        return plan_response(
            registry, req.from_types, req.to_types, policy=policy, traverse=req.traverse
        )

    @app.post("/api/run")
    def api_run(req: RunRequest):
        registry = discover_registry().registry
        try:
            policy = parse_policy(req.policy)
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        if req.batch is not None:
            try:
                return asyncio.run(
                    execute_batch_response(
                        registry,
                        req.have,
                        req.want,
                        req.traverse,
                        req.batch.model_dump(),
                        policy=policy,
                        expand=req.expand,
                        k=req.k,
                        params=req.params,
                        max_expansion=req.max_expansion,
                        review_policy=req.review_policy,
                        confidence_threshold=req.confidence_threshold,
                    )
                )
            except (ValueError, BraidworksError) as exc:
                return {"ok": False, "error": str(exc)}
        if req.traverse:
            return run_traversed_response(
                registry,
                req.have,
                req.want,
                req.traverse,
                policy=policy,
                expand=req.expand,
                k=req.k,
                params=req.params,
                max_expansion=req.max_expansion,
                review_policy=req.review_policy,
                confidence_threshold=req.confidence_threshold,
            )
        return run_response(
            registry,
            req.have,
            req.want,
            policy=policy,
            expand=req.expand,
            k=req.k,
            params=req.params,
            max_expansion=req.max_expansion,
            review_policy=req.review_policy,
            confidence_threshold=req.confidence_threshold,
        )

    @app.post("/api/code")
    def api_code(req: RunRequest):
        try:
            policy = parse_policy(req.policy)
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        if req.batch is not None:
            return batch_code_response(
                discover_registry().registry,
                req.have,
                req.want,
                req.traverse,
                req.batch.model_dump(),
                policy=policy,
                expand=req.expand,
                k=req.k,
                params=req.params,
                max_expansion=req.max_expansion,
                review_policy=req.review_policy,
                confidence_threshold=req.confidence_threshold,
            )
        return code_response(
            discover_registry().registry,
            req.have,
            req.want,
            req.traverse,
            policy=policy,
            expand=req.expand,
            k=req.k,
            params=req.params,
            max_expansion=req.max_expansion,
            review_policy=req.review_policy,
            confidence_threshold=req.confidence_threshold,
        )

    @app.post("/api/run/stream")
    def api_post_run_stream(req: RunRequest):
        async def stream():
            queue = _asyncio.Queue()
            task = None
            try:
                task = _asyncio.create_task(
                    execute_batch_response(
                        discover_registry().registry,
                        req.have,
                        req.want,
                        req.traverse,
                        req.batch.model_dump() if req.batch is not None else None,
                        policy=parse_policy(req.policy),
                        expand=req.expand,
                        k=req.k,
                        params=req.params,
                        max_expansion=req.max_expansion,
                        review_policy=req.review_policy,
                        confidence_threshold=req.confidence_threshold,
                        on_event=lambda event: queue.put_nowait(event),
                    )
                )
                while not (task.done() and queue.empty()):
                    try:
                        event = await _asyncio.wait_for(queue.get(), timeout=0.1)
                        yield f"data: {_json.dumps({'event': 'wave', **event})}\n\n"
                    except TimeoutError:
                        continue
                yield f"data: {_json.dumps({'event': 'done', **await task})}\n\n"
            except (ValueError, BraidworksError) as exc:
                yield f"data: {_json.dumps({'event': 'error', 'error': str(exc)})}\n\n"
            finally:
                if task is not None:
                    if not task.done():
                        task.cancel()
                    await _asyncio.gather(task, return_exceptions=True)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/run/stream")
    def api_run_stream(
        have: str = "{}",
        want: str = "",
        policy: str = "local_first",
        expand: str = "top",
        k: int = 3,
        params: str = "{}",
        max_expansion: int = 10_000,
        review_policy: str = "halt",
        confidence_threshold: float = 0.0,
    ):
        # GET + query params so the browser drives it with a native EventSource (SSE).
        # `have` is a JSON object; `want` is comma-separated.
        def sse(obj) -> str:
            return f"data: {_json.dumps(obj)}\n\n"

        async def stream():
            registry = discover_registry().registry
            try:
                bpolicy = parse_policy(policy)
                review = ReviewPolicy(review_policy)
                have_map = _json.loads(have or "{}")
                supplied_params = _json.loads(params or "{}")
                if not isinstance(have_map, dict) or not isinstance(supplied_params, dict):
                    raise TypeError("have and params must be JSON objects")
            except (ValueError, TypeError) as exc:
                yield sse({"event": "error", "error": str(exc)})
                return
            want_list = [t for t in (want or "").split(",") if t]
            hm, wl, err = _clean_run_inputs(have_map, want_list)
            if err:
                yield sse({"event": "error", "error": err})
                return
            try:
                braid = Braider(registry).plan(frozenset(hm), frozenset(wl), backend_policy=bpolicy)
                caps = {
                    step.capability_id: registry.get_capability(step.weaver_id, step.capability_id)
                    for step in braid.steps
                }
                validated, effective = _effective_parameters(supplied_params, caps)
            except (ValueError, BraidworksError) as exc:
                yield sse({"event": "error", "error": str(exc)})
                return

            queue: _asyncio.Queue = _asyncio.Queue()
            ss = StrandSet.from_strands("e1", [Strand(t, v) for t, v in hm.items()])
            ss.source_row = 1
            task = _asyncio.create_task(
                LocalExecutor(registry).execute(
                    braid,
                    [ss],
                    expand_policy=_expand_policy(expand, k),
                    backend_policy=bpolicy,
                    params=validated,
                    max_expansion=max_expansion,
                    review_policy=review,
                    confidence_threshold=confidence_threshold,
                    on_event=lambda ev: queue.put_nowait(ev),
                )
            )
            try:
                # Drain wave events live until the run finishes, then emit the final payload.
                while not (task.done() and queue.empty()):
                    try:
                        ev = await _asyncio.wait_for(queue.get(), timeout=0.1)
                        yield sse({"event": "wave", **ev})
                    except TimeoutError:
                        continue
                try:
                    result = await task
                except (ValueError, BraidworksError) as exc:
                    yield sse({"event": "error", "error": str(exc)})
                    return
                payload = _run_payload(registry, result, hm, wl, policy=bpolicy)
                yield sse(
                    {
                        "event": "done",
                        **payload,
                        "effective_params": effective,
                        "review_policy": review.value,
                        "confidence_threshold": confidence_threshold,
                    }
                )
            finally:
                if not task.done():
                    task.cancel()
                await _asyncio.gather(task, return_exceptions=True)

        return StreamingResponse(stream(), media_type="text/event-stream")

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
