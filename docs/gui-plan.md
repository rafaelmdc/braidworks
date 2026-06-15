# GUI plan — `weaverkit serve` (issue #87)

## Context

`weaverkit view` today produces a **static, read-only** HTML file (a picture you pan/hover
but can't operate). Issue #87 asks for an **interactive tool**: pick a node, pick what you
want (+ intermediates), and *generate the braid / code* in it — and, tying in the roadmap's
"animate the visualizer" item, watch the braid **light up as it runs**. This doesn't replace
the API or CLI; it's a third interface over the same registry/Braider/executor.

The engine already exists — `view.py` discovers the real registry, embeds the network as
JSON, and runs the real `Braider` for path + run-lineage projections. The *only* missing
piece is interactivity, because a static file can't call back into Python. So we add a tiny
**opt-in local server** that serves the same template wired to a few endpoints. The static
`weaverkit view` export stays exactly as-is.

## Architecture

```
browser (existing canvas UI, extended)  ──HTTP──►  weaverkit serve (FastAPI)  ──►  registry / Braider / LocalExecutor
   GET / : page + embedded network blob       /api/plan   Braider.plan() → build_path() + artifacts/citations
   build · inspect · run · export             /api/run    LocalExecutor.execute() → ExecutionResult.to_json()
   (graph from embedded blob, not fetched)                (all reused from view.py / core; server stays dumb)
```

- **Server:** **FastAPI + uvicorn**, isolated in an optional dependency group so the lean
  core is untouched. FastAPI is async-native (matches the `async` `LocalExecutor.execute` —
  `await` directly, no `asyncio.run`/queue bridge), gives native SSE via `StreamingResponse`,
  and validates payloads with Pydantic.
  - `pyproject.toml`: `[project.optional-dependencies] serve = ["fastapi", "uvicorn"]`.
    Base `weaverkit` stays **stdlib-only** — no new deps for weavers / conformance / scaffold
    / CI; only `pip install weaverkit[serve]` pulls them.
  - `serve.py` imports fastapi/uvicorn **lazily**; `weaverkit serve` without the extra prints
    a clear `install weaverkit[serve]` message (mirrors how optional backends degrade).
  - Bind `127.0.0.1` only (localhost, opt-in). New CLI subcommand
    `weaverkit serve [--port 8765] [--no-open]`, wired in `cli.py` next to `cmd_view`.
- **Front-end:** extend the existing vanilla-canvas template (`_view_template.py`) — no
  framework (React stays "later"). Add a builder side-panel + results panel; swap the embedded
  static data blob for `fetch('/api/...')` when served (feature-detect `location.protocol` so
  the file still works offline with its inlined blob).

---

## Complexity budget & optimizations (read before building)

The endpoints are thin wrappers over functions that already exist (`build_network`,
`build_path`, `Braider.plan`, `references_for`, `LocalExecutor.execute`). **The real work and
risk is the front-end** (canvas interaction state, panels). So: keep the server dumb, and
delete every avoidable moving part. Decisions baked into the plan below:

1. **No `/api/network` endpoint.** The server renders the page with the real network blob
   already injected (reuse `render_html`), so the front-end reads the *embedded* blob for the
   graph — same code path as the static export. Only the *actions* (`/api/plan`, `/api/run`)
   are dynamic. Removes an endpoint and the static/served dual-mode branch for the graph.
2. **All derived text is computed server-side**, returned in the `/api/plan` response:
   `artifacts` (CLI line + Python + braid JSON), `citations` (`references_for`), and the
   "why no path" message (`str(NoPathError)`, already produced by `build_data`). The JS just
   displays strings — no CLI-arg logic, no reference rendering duplicated in JS.
3. **Endpoint logic lives in plain, FastAPI-free functions** (e.g. `plan_response(registry,
   frm, to) -> dict`); the FastAPI layer is a 5-line adapter. So **most tests need no `[serve]`
   extra** — only one or two smoke tests do (skip if uninstalled). Keeps CI lean.
4. **Light-up = client-side replay, not streaming (Phase 2).** `/api/run` returns the final
   `ExecutionResult.to_json()` (one `await`); the front-end *animates* the light-up by replaying
   the per-step `completion[]` metadata wave-by-wave on a timer. **This needs no core change and
   no SSE** — and for any sub-~10s braid it's visually identical to true streaming. Real-time
   SSE + the `on_event` core hook becomes an *optional* Phase 2b, only if long braids demand it.
5. **Reuse, don't reimplement:** the canvas already hit-tests nodes (hover/drag) — reuse it to
   capture clicks; the static view already draws a highlighted `path` — feed `build_path`'s
   output into that same renderer. Results/export reuse the `braidworks` CLI's `json`/`tsv`
   formatting (factor the formatter into a shared helper rather than duplicating).
6. **Params form is bounded:** render fields only for the planned route's steps that declare
   `parameters` (already in the network blob) — not a generic editor.

---

## Phase 1 — Build & inspect (no execution; **no core changes**)

The whole value of #87 — design a braid, see it, get the code — needs no run and no core edit.

- **`weaverkit serve`** (`cli.py` + new `serve.py`):
  - `GET /` → template rendered with the real network blob injected (reuse `render_html`).
  - `POST /api/plan` `{from, to, intermediates, policy, params}` → `Braider.plan(...)` projected
    with the existing `build_path(...)`; returns `{path, artifacts, citations, error?}` — all
    derived text computed server-side (opt. 2).
- **Builder UI:** click a node → **have**, shift-click → **want**; optional **intermediates**
  (ordered waypoints, planned as segments); optional **params** form (from each step's declared
  `parameters`). "Plan" highlights the returned route on the graph.
- **Artifact emit** ("generate the code/braids"): from the resolved braid, three copyable blocks
  — the **`braidworks weave --have … --want … [--param …]`** CLI line, a **Python snippet**
  (registry + `Braider` + `LocalExecutor`), and the raw **braid JSON**.
- **Citations / provenance panel** *(plan-time — no run needed)*: the braid's weavers are known
  from the plan, so `references_for(weaver_ids, registry)` yields the sources to cite.
  `build_network` already attaches each weaver's rendered reference — surface it.
- **"Why no path?" explainer:** on `NoPathError`/`NoPlanError`, show *which key* is the island
  and the nearest reachable target (reuse the planner's existing error classification) instead
  of a dead end.
- **Shareable deep-link URL:** encode `from`/`want`/`params` in the URL hash so a built braid is
  a paste-able link (pure front-end).

*Ships alone: a real design tool. `weaverkit` minor bump.*

---

## Phase 2 — Run & watch (**no core change** — replay-animated light-up)

- **`POST /api/run`** `{from, want, params, expand}` → build StrandSets (reuse `--have`/batch
  logic from `braidworks-core/cli.py`), `await executor.execute(...)`, return
  `ExecutionResult.to_json()` (plus the run-lineage projection from `build_run_views`).
- **Light-up (replay):** the front-end animates the path **wave by wave** on a timer, driven by
  the returned per-step `completion[]`/`produced` metadata (opt. 4). Error-tolerance shows for
  free — a failed step's node paints red, the reroute lights the fallback edge.
- **Results table:** resolved strands/values per entity (the real answer) — the dossier.
- **Export (CSV / TSV / JSON):** reuse the `braidworks` CLI `json`/`tsv` formatter (shared helper).
- **Fan-out control (`ExpandPolicy`: top / top-k / all):** drives the "TP53 across N orthologs,
  each with its structure" act; passed to `/api/run`.

*Stacks on Phase 1. `weaverkit` minor bump only — no core change.*

## Phase 2b — Real-time streaming (optional; only if long braids need it)

If a braid runs long enough that "finish then replay" feels laggy, upgrade to true streaming:
add an optional `on_event` callback to `LocalExecutor.execute` (default `None` = unchanged) and
stream it over SSE via FastAPI `StreamingResponse`. Same front-end light-up, fed live instead of
replayed. *`braidworks-core` minor bump (the hook) + `weaverkit` patch.* Deferred until proven needed.

---

## Phase 3 — Persistence & scale (defer; real scope, not demo-critical)

- **Save / load braids as named recipes** — a small library to rerun built braids later.
- **Graph search / filter** — pays off once the network grows past ~12 weavers.

---

## Guardrails
- Localhost-only, opt-in; the static `weaverkit view` export is untouched and stays offline.
- FastAPI/uvicorn live **only** in the `[serve]` extra — base `weaverkit` stays stdlib-only,
  so weavers, conformance, scaffold, and CI gain no deps.
- Front-end stays vanilla canvas (extend `_view_template.py`); React only if it later earns it.
- Each phase ships independently (Phase 1 needs no core change at all).

## Files
- `weaverkit/src/weaverkit/serve.py` — **new**: plain `plan_response()` / `run_response()`
  functions (FastAPI-free, testable) + a thin FastAPI adapter (lazy import). Reuses
  `view.discover_registry/build_network/build_path`, `core.Braider`, `core.references_for`.
- `weaverkit/src/weaverkit/cli.py` — **edit**: `cmd_serve` + `serve` subparser (next to `view`).
- `weaverkit/src/weaverkit/_view_template.py` — **edit**: builder + results panels, click-to-set
  have/want, route highlight (reuse path renderer), replay light-up, deep-link hash. Keep the
  offline static path intact.
- `weaverkit/pyproject.toml` — **edit**: `[serve]` optional-dependency group.
- shared results formatter — factor the `braidworks` CLI's `json`/`tsv` rendering into a reused
  helper (avoid duplicating in serve).
- *(Phase 2b only, deferred)* `braidworks-core/.../executor.py` — optional `on_event` callback.
- Tests: `weaverkit/tests/test_serve.py` — most assert on the plain `plan_response`/`run_response`
  dicts (no extra needed); one smoke test via FastAPI `TestClient` skipped if `[serve]` absent.

## Verify
- Phase 1: `weaverkit serve` → open `http://127.0.0.1:8765`, build `protein.query → pdb.id`,
  confirm the route highlights, the citations panel lists UniProt/PDBe, and the emitted CLI line
  actually runs (`braidworks weave …`). Try an impossible target → "why no path" names the island.
- Phase 2: run `gene.ncbi.id → protein.uniprot.accession → structure`, watch nodes light up
  wave-by-wave, flip the fan-out to "all", read the results table, export CSV. Kill a backend's
  network → failed node paints red + reroutes.
- `weaverkit/tests/test_serve.py` green; existing `test_view.py` unaffected (static export
  unchanged); full `make test` + `make lint` green.
