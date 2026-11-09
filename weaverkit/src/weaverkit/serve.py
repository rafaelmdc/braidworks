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
import errno
import io
import os
import secrets
import socket
import sqlite3
import sys
from collections import OrderedDict
from dataclasses import replace

from braidworks.core.braid import BackendPolicy
from braidworks.core.exceptions import BraidworksError, NoPathError, NoPlanError
from braidworks.core.executor import (
    ExecutionResult,
    ExpandPolicy,
    ReviewPolicy,
)
from braidworks.core.inputs import read_input_rows, row_label
from braidworks.core.outcomes import execution_records
from braidworks.core.persistence_options import QueryPersistence
from braidworks.core.query import (
    QueryOptions,
    QueryRequest,
    normalize_expansion,
)
from braidworks.core.references import references_for
from braidworks.core.review import ReviewDecision
from braidworks.core.run_store import SQLiteRunStore, run_status
from braidworks.core.strand import Strand, StrandSet
from braidworks.core.traverse import resolve_traversal, traversal_route_capabilities

from weaverkit.codegen import cli_artifact, path_artifact, python_artifact
from weaverkit.streaming import sse_events
from weaverkit.view import (
    build_data,
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


def _session(registry, policy=BackendPolicy.LOCAL_FIRST):
    """The same Session the Python API and CLI use, over this request's registry.

    Coroutines are awaited on the caller's loop, so no private loop thread is started and
    nothing needs closing; the registry stays the caller's.
    """
    from braidworks._session import Session

    return Session(registry=registry, backend=BackendPolicy(policy).value)


def _prepare_experiment(registry, have, want, traverse, batch=None, **options):
    sets = (
        batch_inputs(have, batch)
        if batch is not None
        else [
            StrandSet.from_strands(
                row_label(have) if have else "e1",
                [Strand(key, value) for key, value in have.items()],
            )
        ]
    )
    if not sets[0].available_types() or (not want and not traverse):
        raise ValueError("choose inputs and outputs or a pass-through step")
    for i, ss in enumerate(sets, 1):
        ss.source_row = i
    return _session(registry, options.get("policy", BackendPolicy.LOCAL_FIRST))._prepare_request(
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
        )
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
    persistence=None,
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
        "persistence": persistence,
    }
    return _code_response(registry, have, want, traverse, None, options, _prepared)


def _code_response(registry, have, want, traverse, batch, options, prepared=None):
    try:
        prepared = prepared or _prepare_experiment(registry, have, want, traverse, batch, **options)
        settings = prepared.request.options
        persistence = _persistence(options.get("persistence"))
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
                "cli_weave": cli_artifact(prepared, have, batch=batch, persistence=persistence),
                "cli_path": path_artifact(prepared, have, batch=batch),
                "python": python_artifact(prepared, persistence=persistence),
                "braid": recipe,
            },
        }
    except (ValueError, BraidworksError, OSError, sqlite3.Error, KeyError) as exc:
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
            row_label(row),
            [Strand(key, value) for key, value in {**have, **row}.items()],
        )
        ss.source_row = i
        sets.append(ss)
    return sets


def _checkpoint_events(on_event, saved=None):
    def checkpoint(cp):
        if saved is not None:
            saved[:] = [cp]
        if on_event:
            on_event(
                {
                    "event": "checkpoint",
                    "run_id": cp.run_id,
                    "revision": cp.revision,
                    "status": cp.status,
                }
            )

    return checkpoint


# Results with rows paused for review, kept so the page can resume them with the
# reviewer's choices (Python's ``result.resume()``). Bounded: the oldest is dropped.
_PAUSED: OrderedDict[str, object] = OrderedDict()
PAUSED_LIMIT = 32


def _hold(outcome) -> str:
    token = secrets.token_urlsafe(16)
    _PAUSED[token] = outcome
    while len(_PAUSED) > PAUSED_LIMIT:
        _PAUSED.popitem(last=False)
    return token


def _review_items(outcome) -> list[dict]:
    """Each paused row with what a reviewer needs: input, step, candidates, decision key."""
    return [
        {
            "key": item._key,
            "input": item.input,
            "row": item.row,
            "step": item.step,
            "ambiguous": item.ambiguous,
            "candidates": item.candidates,
            "warnings": item.warnings,
        }
        for item in outcome.review
    ]


def result_table(outcome) -> dict:
    """``Result`` rows as the browser shows them, plus exact Python exports.

    ``rows`` is ``Result.to_json()["rows"]``; ``sizes`` gives each list cell's length,
    true ``total`` and ``complete`` flag (JSON keeps a ``Listing`` as a plain list), and
    ``exports`` are byte-for-byte ``to_csv()`` / ``to_csv(sep="\t")`` / ``to_json()``.
    """
    import json

    from braidworks import Listing

    document = outcome.to_json()
    sizes = [
        {
            key: {"shown": len(value), "total": value.total, "complete": value.complete}
            for key, value in row.items()
            if isinstance(value, Listing)
        }
        for row in outcome.rows
    ]
    return {
        "table": {
            "summary": document["summary"],
            "want": document["want"],
            "columns": outcome.columns,
            "rows": json.loads(json.dumps(document["rows"], ensure_ascii=False)),
            "sizes": sizes,
            "references": document["references"],
            "review": json.loads(json.dumps(_review_items(outcome), ensure_ascii=False)),
        },
        "exports": {
            "csv": outcome.to_csv(),
            "tsv": outcome.to_csv(sep="\t"),
            "json": json.dumps(document, ensure_ascii=False, indent=2),
        },
    }


def step_outcomes(raw) -> dict[str, dict]:
    """What each capability did across the final rows: statuses, backends and errors.

    Counts come from each terminal row's completion records (``ok`` / ``no_match`` /
    ``skipped``) and from the errors list (``recovered`` when the run rerouted around it).
    """
    out: dict[str, dict] = {}

    def entry(capability_id):
        return out.setdefault(
            capability_id, {"statuses": {}, "backends": {}, "errors": 0, "recovered": 0}
        )

    from braidworks.core.strand import entity_key

    terminal = [
        *raw.resolved,
        *(ss for ss, _ in raw.unresolved),
        *(item.strand_set for item in raw.review_queue),
        *(error.strand_set for error in raw.errors if not error.recovered),
    ]
    rows = list({entity_key(ss): ss for ss in terminal}.values())  # one per final row
    for ss in rows:
        for step in ss.completion:
            counts = entry(step.capability_id)
            counts["statuses"][step.status] = counts["statuses"].get(step.status, 0) + 1
            if step.backend:
                counts["backends"][step.backend] = counts["backends"].get(step.backend, 0) + 1
    for error in raw.errors:
        if error.capability_id:
            entry(error.capability_id)["recovered" if error.recovered else "errors"] += 1
    return out


def _query_payload(registry, prepared, outcome, want, *, run=None) -> dict:
    """The browser's response for an executed (or resumed) prepared query."""
    options = prepared.request.options
    raw = outcome.raw
    payload = _traverse_payload(registry, raw, want, [cid for _, cid in prepared.traversals])
    if len(prepared.plans) == 1:
        payload["path"] = render_path(registry, prepared.plans[0][0], policy=options.backend_policy)
    payload["summary"]["inputs"] = len(prepared.request.inputs)
    return {
        **payload,
        **result_table(outcome),
        "effective_params": _prepared_effective(registry, prepared),
        "planned_routes": [braid.to_json() for braid, _ in prepared.plans],
        "step_outcomes": step_outcomes(raw),
        **({"run": run_status(run)} if run is not None else {}),
        "review_policy": options.review_policy.value,
        "confidence_threshold": options.confidence_threshold,
    }


async def execute_query_response(
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
    persistence=None,
):
    """The one run path: plan every row group before I/O, then execute through ``Session``.

    Single inputs, traversals, batches, saved runs and streamed runs all come here.
    """
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
    saved: list = []
    outcome = await _session(registry, policy)._execute(
        prepared,
        list(want),
        persistence=_persistence(persistence),
        on_saved=_checkpoint_events(on_event, saved),
        on_event=on_event,
    )
    payload = _query_payload(registry, prepared, outcome, want, run=saved[-1] if saved else None)
    if outcome.review and not saved:  # a saved run resumes from its store instead
        payload["review_token"] = _hold(outcome)
    return payload


async def execute_review_response(token: str, decisions) -> dict:
    """Record review choices on a held result and continue its paused rows.

    ``decisions`` use the saved-run format (``ReviewDecision.to_json()``); rows without a
    decision stay paused, and the response carries a fresh ``review_token`` for them.
    """
    outcome = _PAUSED.pop(token, None)
    if outcome is None:
        raise ValueError("this review is no longer held by the server; run the query again")
    items = {item._key: item for item in outcome.review}
    try:
        for data in decisions or ():
            decision = ReviewDecision.from_json(data)
            item = items.get(decision.entity_key)
            if item is None:
                raise ValueError(f"no paused row has key {decision.entity_key!r}")
            if decision.action == "select":
                item.choose(decision.candidate_index)
            elif decision.action == "accept":
                item.accept()
            else:
                item.reject()
        if not outcome._decisions:
            raise ValueError("choose, accept or reject at least one paused row")
    except ValueError:
        _PAUSED[token] = outcome  # a bad request keeps the review available
        raise
    session = outcome._session
    resumed = await session._continue(outcome)
    payload = _query_payload(session.registry, resumed._prepared, resumed, resumed.want)
    if resumed.review:
        payload["review_token"] = _hold(resumed)
    return payload


# The batch endpoint's original name; every run now shares one path.
execute_batch_response = execute_query_response


def _persistence(value):
    try:
        return (
            value
            if isinstance(value, QueryPersistence)
            else (QueryPersistence.from_json(value) if value is not None else QueryPersistence())
        )
    except (TypeError, AttributeError) as exc:
        raise ValueError(
            "Invalid persistence configuration; use a versioned options object"
        ) from exc


async def execute_resume_response(registry, run_id, persistence, decisions=(), *, on_event=None):
    """Continue a saved run through ``Session`` (applying any review decisions)."""
    checkpoint, outcome = await _session(registry)._resume_run(
        run_id,
        _persistence(persistence),
        decisions=tuple(
            decision if isinstance(decision, ReviewDecision) else ReviewDecision.from_json(decision)
            for decision in decisions
        ),
        on_saved=_checkpoint_events(on_event),
        on_event=on_event,
    )
    prepared = checkpoint.definition.prepared
    return _query_payload(
        registry, prepared, outcome, sorted(prepared.request.targets), run=checkpoint
    )


def _clean_run_inputs(have: dict, want: list) -> tuple[dict, list, str | None]:
    """Normalize have/want; return ``(have, want, error)`` (error set if either is empty)."""
    have = {str(t): v for t, v in (have or {}).items() if str(t).strip()}
    want = [str(t) for t in (want or [])]
    if not have or not want:
        return have, want, "enter a value for at least one Have type and a Want type"
    return have, want, None


def _run_sync(registry, have, want, traverse, **options) -> dict:
    try:
        return asyncio.run(execute_query_response(registry, have, want, traverse, None, **options))
    except (ValueError, BraidworksError, OSError, sqlite3.Error, KeyError) as exc:
        return {"ok": False, "error": str(exc)}


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

    Returns ``{"ok": True, "path", "result", "runs", "columns", "rows", "summary", …}`` —
    ``result`` is ``ExecutionResult.to_json()`` (carries the per-step ``completion`` the
    front-end replays as the light-up), ``runs`` the fan-out lineage views, ``rows`` the
    flat results table. ``{"ok": False, "error"}`` when unroutable. Sync (drives the one
    async run path via ``asyncio.run``), so it is unit-testable without the web dependency.
    """
    have, want, err = _clean_run_inputs(have, want)
    if err:
        return {"ok": False, "error": err}
    return _run_sync(
        registry,
        have,
        want,
        [],
        policy=policy,
        expand=expand,
        k=k,
        params=params,
        max_expansion=max_expansion,
        review_policy=review_policy,
        confidence_threshold=confidence_threshold,
    )


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
    the fanned entities). Same shape as :func:`run_response`; ``path`` is ``None``
    because a traversal is not a single route.
    """
    have = {str(t): v for t, v in (have or {}).items() if str(t).strip()}
    want = [str(t) for t in (want or [])]
    tokens = [str(t) for t in (traverse or []) if str(t).strip()]
    if not have or not tokens:
        return {"ok": False, "error": "pass-through needs a Have value and at least one step"}
    return _run_sync(
        registry,
        have,
        want,
        tokens,
        policy=policy,
        expand=expand,
        k=k,
        params=params,
        max_expansion=max_expansion,
        review_policy=review_policy,
        confidence_threshold=confidence_threshold,
    )


def find_response(registry, text: str, limit: int = 10) -> dict:
    """Fields matching plain words, best first — the same ranking as ``bw.find``."""
    if not str(text or "").strip():
        return {"ok": False, "error": "type a few words to search for, e.g. pdb structures"}
    if not 1 <= int(limit) <= 100:
        return {"ok": False, "error": "limit must be between 1 and 100"}
    return {"ok": True, "matches": _session(registry).find(str(text), limit=int(limit)).to_json()}


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


# --- browser-supplied file paths --------------------------------------------


def confine_path(path: str, root: str) -> str:
    """Resolve a browser-supplied path inside ``root`` (the server's data directory).

    Relative paths resolve against ``root``; anything that resolves outside it (absolute
    paths elsewhere, ``..``, symlinks out) is refused, so a page that can reach the
    server cannot make it open or create files elsewhere on its disk.
    """
    candidate = os.path.realpath(os.path.join(root, path))
    if candidate != root and not candidate.startswith(root + os.sep):
        raise ValueError(
            f"path {path!r} is outside the server's data directory ({root}); "
            "use a path inside it, or restart with --data-dir"
        )
    return candidate


def confine_persistence(value, root: str):
    """Browser persistence options with their cache/run paths confined to ``root``."""
    if value is None:
        return None
    options = _persistence(value)
    return replace(
        options,
        cache_db=confine_path(options.cache_db, root) if options.cache_db else None,
        run_db=confine_path(options.run_db, root) if options.run_db else None,
    ).to_json()


# --- FastAPI adapter (optional; lazy import) ---------------------------------


def _notice_html(notice: str) -> str:
    import html

    return (
        '<div role="status" style="position:fixed;bottom:0;left:0;right:0;z-index:50;'
        "font:600 13px system-ui,sans-serif;padding:8px 12px;background:#8a5a00;"
        f'color:#fff;text-align:center">{html.escape(notice)}</div>'
    )


def create_app(
    data_dir: str | os.PathLike | None = None,
    *,
    registry=None,
    examples: list[dict] | None = None,
    notice: str | None = None,
):
    """Build the FastAPI app. Raises a clear error if the ``[serve]`` extra is missing.

    ``data_dir`` (default: the current directory) bounds every cache/run file path the
    browser supplies; see :func:`confine_path`. ``registry`` fixes the sources (the
    offline demo passes its fixture registry); by default they are discovered per
    request. ``examples`` replaces the built-in example cards and ``notice`` shows a
    banner on every page.
    """
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
        persistence: dict | None = None
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

    class ResumeRequest(BaseModel):
        model_config = {"extra": "forbid"}
        run_id: str
        persistence: dict
        decisions: list[dict] = Field(default_factory=list)

    root = os.path.realpath(data_dir if data_dir is not None else os.getcwd())

    def _registry():
        return registry if registry is not None else discover_registry().registry

    app = FastAPI(title="weaverkit serve", docs_url=None, redoc_url=None)

    # "/" is the form-first lookup page; the network graph (with the builder slotted in,
    # interactive=True) is the optional Explore view at "/explore".
    from weaverkit._lookup_ui import render_lookup_page

    _landing = render_lookup_page(_registry(), examples=examples, notice=notice)
    _explore = render_html(build_data(registry=registry), interactive=True).replace(
        "<body>",
        '<body><a href="/" style="position:fixed;top:8px;right:12px;z-index:50;'
        "font:600 13px system-ui,sans-serif;padding:6px 12px;border-radius:6px;"
        'background:#0b6870;color:#fff;text-decoration:none">\u2190 Look up</a>'
        + (_notice_html(notice) if notice else ""),
        1,
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _landing

    @app.get("/explore", response_class=HTMLResponse)
    def explore() -> str:
        return _explore

    @app.post("/api/plan")
    def api_plan(req: PlanRequest):
        registry = _registry()
        try:
            policy = parse_policy(req.policy)
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        return plan_response(
            registry, req.from_types, req.to_types, policy=policy, traverse=req.traverse
        )

    @app.get("/api/find")
    def api_find(q: str = "", limit: int = 10):
        return find_response(_registry(), q, limit)

    @app.post("/api/run")
    def api_run(req: RunRequest):
        registry = _registry()
        try:
            policy = parse_policy(req.policy)
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        if req.batch is not None or req.persistence is not None:
            try:
                persistence = confine_persistence(req.persistence, root)
                return asyncio.run(
                    execute_query_response(
                        registry,
                        req.have,
                        req.want,
                        req.traverse,
                        req.batch.model_dump() if req.batch is not None else None,
                        policy=policy,
                        expand=req.expand,
                        k=req.k,
                        params=req.params,
                        max_expansion=req.max_expansion,
                        review_policy=req.review_policy,
                        confidence_threshold=req.confidence_threshold,
                        persistence=persistence,
                    )
                )
            except (ValueError, BraidworksError, OSError, sqlite3.Error, KeyError) as exc:
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
                _registry(),
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
                persistence=req.persistence,
            )
        return code_response(
            _registry(),
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
            persistence=req.persistence,
        )

    @app.get("/api/runs")
    def api_runs(run_db: str):
        try:
            store = SQLiteRunStore(confine_path(run_db, root), create=False)
            return {"ok": True, "runs": [run_status(cp) for cp in store.list()]}
        except (ValueError, OSError, sqlite3.Error) as exc:
            return {"ok": False, "error": str(exc)}

    @app.get("/api/run/status")
    def api_run_status(run_db: str, run_id: str):
        try:
            return {
                "ok": True,
                "run": run_status(
                    SQLiteRunStore(confine_path(run_db, root), create=False).load(run_id)
                ),
            }
        except (ValueError, OSError, sqlite3.Error, KeyError) as exc:
            return {"ok": False, "error": str(exc)}

    class ReviewRequest(BaseModel):
        model_config = {"extra": "forbid"}
        token: str
        decisions: list[dict] = Field(default_factory=list)

    @app.post("/api/review")
    def api_review(req: ReviewRequest):
        try:
            return asyncio.run(execute_review_response(req.token, req.decisions))
        except (ValueError, BraidworksError, OSError, sqlite3.Error, KeyError) as exc:
            return {"ok": False, "error": str(exc)}

    @app.post("/api/resume")
    def api_resume(req: ResumeRequest):
        try:
            return asyncio.run(
                execute_resume_response(
                    _registry(),
                    req.run_id,
                    confine_persistence(req.persistence, root),
                    req.decisions,
                )
            )
        except (ValueError, BraidworksError, OSError, sqlite3.Error, KeyError) as exc:
            return {"ok": False, "error": str(exc)}

    @app.post("/api/resume/stream")
    def api_resume_stream(req: ResumeRequest):
        async def execute(on_event):
            return await execute_resume_response(
                _registry(),
                req.run_id,
                confine_persistence(req.persistence, root),
                req.decisions,
                on_event=on_event,
            )

        return StreamingResponse(sse_events(execute), media_type="text/event-stream")

    @app.post("/api/run/stream")
    def api_post_run_stream(req: RunRequest):
        async def execute(on_event):
            return await execute_query_response(
                _registry(),
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
                persistence=confine_persistence(req.persistence, root),
                on_event=on_event,
            )

        return StreamingResponse(sse_events(execute), media_type="text/event-stream")

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
        async def execute(on_event):
            have_map = _json.loads(have or "{}")
            supplied_params = _json.loads(params or "{}")
            if not isinstance(have_map, dict) or not isinstance(supplied_params, dict):
                raise ValueError("have and params must be JSON objects")  # noqa: TRY004 - public input error
            hm, wl, error = _clean_run_inputs(have_map, [t for t in (want or "").split(",") if t])
            if error:
                raise ValueError(error)
            return await execute_query_response(
                _registry(),
                hm,
                wl,
                [],
                None,
                policy=parse_policy(policy),
                expand=expand,
                k=k,
                params=supplied_params,
                max_expansion=max_expansion,
                review_policy=review_policy,
                confidence_threshold=confidence_threshold,
                on_event=on_event,
            )

        return StreamingResponse(sse_events(execute), media_type="text/event-stream")

    return app


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def exposure_warning(host: str, data_dir: str) -> str | None:
    """What a non-loopback bind exposes, in plain words; ``None`` for localhost."""
    if host in LOOPBACK_HOSTS:
        return None
    return (
        f"warning: serving on {host} makes this server reachable from other machines. "
        "Anyone who can reach it can run queries through your configured sources, read "
        f"error messages, and create cache/run files inside {data_dir}. "
        "Use the default --host 127.0.0.1 unless you trust the network."
    )


class PortInUseError(RuntimeError):
    """The requested port is taken; raised before any URL is announced."""


def bind_port(host: str, port: int) -> socket.socket:
    """Bind and listen on ``host:port`` now, so a busy port fails before anything prints.

    The bound socket is handed to uvicorn, so nothing can take the port in between.
    """
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    if os.name != "nt":  # on Windows SO_REUSEADDR would let us share a busy port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        sock.listen(2048)
    except OSError as exc:
        sock.close()
        if exc.errno in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", None)):
            raise PortInUseError(
                f"port {port} is already in use on {host}: another server (perhaps an "
                f"earlier `braidworks serve`) is running there. Stop it (`make serve-stop`) "
                f"or choose another port, e.g. --port {port + 1}."
            ) from exc
        raise PortInUseError(f"cannot listen on {host}:{port}: {exc.strerror or exc}") from exc
    return sock


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    data_dir: str | os.PathLike | None = None,
    registry=None,
    examples: list[dict] | None = None,
    notice: str | None = None,
) -> None:
    """Run the GUI server on localhost. Requires the ``[serve]`` extra.

    ``data_dir`` (default: the current directory) is the only place browser-supplied
    cache and run files may live. ``registry``, ``examples`` and ``notice`` are as for
    :func:`create_app`.
    """
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(_SERVE_EXTRA_HINT) from exc

    root = os.path.realpath(data_dir if data_dir is not None else os.getcwd())
    warning = exposure_warning(host, root)
    if warning:
        print(warning, file=sys.stderr)
    app = create_app(data_dir=root, registry=registry, examples=examples, notice=notice)
    # Bind first: a busy port must fail here, before a URL is printed or a browser opens.
    sock = bind_port(host, port)
    bound = sock.getsockname()[1]
    url = f"http://[{host}]:{bound}" if ":" in host else f"http://{host}:{bound}"
    if open_browser:
        import threading
        import webbrowser

        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    if notice:
        print(notice, flush=True)
    print(f"braidworks serve — open {url}  (Ctrl-C to stop)", flush=True)
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=bound, log_level="warning"))
    server.run(sockets=[sock])
