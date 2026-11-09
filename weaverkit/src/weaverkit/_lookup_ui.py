"""The browser's form-first landing page: paste IDs → say what they are → pick fields → run.

Served at ``/`` by ``braidworks serve``; the network graph lives at ``/explore``. The page
is self-contained (no external fonts or scripts). The installed field catalogue is
injected at render time so input types and reachability show without a request; field
search, route planning and runs use ``/api/find``, ``/api/plan`` and ``/api/run/stream``.
"""

from __future__ import annotations

import json

from braidworks.core.catalog import field_catalog
from braidworks.core.registry import BraidRegistry

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Braidworks</title>
<style>
/* One working column: the form reads top-down (IDs → type → fields → run); results open
   beneath it. Colours are tokens, redefined for dark mode. */
:root {
  --bg: #f4f6f4; --panel: #ffffff; --ink: #17211e; --muted: #5b6863; --line: #d9dfdb;
  --accent: #0b6870; --accent-ink: #ffffff; --accent-soft: #e2f0f0;
  --ok: #1f7a45; --ok-soft: #e3f3e8; --warn: #9a5b00; --warn-soft: #fbefd9;
  --none: #59636b; --none-soft: #eceff1; --err: #b3261e; --err-soft: #fbe5e3;
  --sans: "Public Sans", "Segoe UI", system-ui, -apple-system, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) { :root {
  --bg: #111816; --panel: #18211e; --ink: #e4ebe8; --muted: #9aa8a3; --line: #2c3834;
  --accent: #5cc3c9; --accent-ink: #062224; --accent-soft: #163536;
  --ok: #6fd39a; --ok-soft: #173426; --warn: #f0b75c; --warn-soft: #3a2c14;
  --none: #a9b4bb; --none-soft: #252d31; --err: #ff8a80; --err-soft: #3d1f1d;
  color-scheme: dark; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 var(--sans); }
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 max(16px, env(safe-area-inset-left)) 48px; }
code, .mono { font-family: var(--mono); font-size: 0.88em; }
h1, h2, h3 { margin: 0; text-wrap: balance; }
button { font: inherit; cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
[hidden] { display: none !important; }
.top { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 24px; padding-block: 14px; border-bottom: 1px solid var(--line); }
.brand { font-weight: 700; font-size: 19px; letter-spacing: -0.01em; }
.nav { display: flex; gap: 4px; }
.nav a { color: var(--muted); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-weight: 500; }
.nav a[aria-current="page"] { background: var(--accent-soft); color: var(--accent); }
.intro { display: grid; gap: 6px; padding-block: 26px 16px; }
.intro h1 { font-size: clamp(24px, 4vw, 32px); letter-spacing: -0.02em; }
.intro p { margin: 0; color: var(--muted); max-width: 66ch; }
.form { display: grid; gap: 14px; }
.step { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px; display: grid; gap: 12px; min-width: 0; }
.step-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.num { font-family: var(--mono); font-size: 12px; color: var(--accent); border: 1px solid var(--accent); border-radius: 99px; width: 22px; height: 22px; display: inline-grid; place-items: center; flex: none; }
.step h2 { font-size: 17px; }
.hint { color: var(--muted); font-size: 13.5px; }
textarea { width: 100%; min-height: 110px; resize: vertical; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; background: var(--bg); color: var(--ink); font: 14px/1.6 var(--mono); }
.row { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; }
.ghost { border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 7px; padding: 6px 12px; font-size: 13.5px; }
.ghost:hover { border-color: var(--accent); color: var(--accent); }
.count { font-size: 13.5px; color: var(--muted); }
.count b { color: var(--ink); font-variant-numeric: tabular-nums; }
.types { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 8px; }
.type { text-align: left; border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 8px; padding: 10px 12px; display: grid; gap: 3px; }
.type .tid { font-family: var(--mono); font-size: 12.5px; font-weight: 600; }
.type .desc { font-size: 13px; color: var(--muted); }
.type[aria-checked="true"] { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); background: var(--accent-soft); }
select, input[type="search"], input[type="text"], input[type="number"] { border: 1px solid var(--line); border-radius: 7px; padding: 7px 10px; background: var(--bg); color: var(--ink); font: inherit; font-size: 14px; }
.search { width: 100%; }
.chosen { display: flex; flex-wrap: wrap; gap: 6px; min-height: 30px; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: 6px; background: var(--accent-soft); color: var(--accent); border-radius: 99px; padding: 3px 4px 3px 10px; font: 12.5px var(--mono); }
.chip button { border: 0; background: none; color: inherit; width: 20px; height: 20px; border-radius: 99px; line-height: 1; }
.chip button:hover { background: var(--accent); color: var(--accent-ink); }
.matches { display: grid; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.match { display: grid; grid-template-columns: auto 1fr; gap: 2px 12px; padding: 9px 12px; border-top: 1px solid var(--line); align-items: start; cursor: pointer; }
.match:first-child { border-top: 0; }
.match:hover { background: var(--bg); }
.match input { margin-top: 4px; accent-color: var(--accent); }
.match .tid { font-family: var(--mono); font-size: 13px; font-weight: 500; }
.match .meta { grid-column: 2; font-size: 12.5px; color: var(--muted); }
.match.off { opacity: 0.55; cursor: not-allowed; }
.noroute { color: var(--warn); }
.options { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px 16px; }
.options label { display: grid; gap: 4px; font-size: 13.5px; }
.options .note { color: var(--muted); font-size: 12.5px; }
.problem { color: var(--warn); font-size: 13.5px; white-space: pre-line; }
.runbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; padding: 14px 20px; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
.run { border: 0; background: var(--accent); color: var(--accent-ink); border-radius: 8px; padding: 10px 18px; font-weight: 600; font-size: 15px; }
.run:disabled { opacity: 0.45; cursor: not-allowed; }
.progress { font-size: 13.5px; color: var(--muted); }
.progress.error { color: var(--err); }
.results { display: grid; gap: 14px; padding-top: 26px; }
.rhead { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; justify-content: space-between; }
.rhead h2 { font-size: 22px; }
.summary { font-size: 14px; color: var(--muted); font-variant-numeric: tabular-nums; }
.tablebox { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; overflow-x: auto; min-width: 0; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { text-align: left; vertical-align: top; padding: 10px 12px; border-top: 1px solid var(--line); }
thead th { border-top: 0; font-weight: 600; font-size: 12px; color: var(--muted); background: var(--bg); white-space: nowrap; }
thead th code { color: var(--ink); }
td.input { font-family: var(--mono); font-weight: 500; white-space: nowrap; }
.status { display: inline-block; border-radius: 5px; padding: 1px 8px; font-size: 12px; font-weight: 600; }
.s-resolved { background: var(--ok-soft); color: var(--ok); }
.s-review { background: var(--warn-soft); color: var(--warn); }
.s-unresolved { background: var(--none-soft); color: var(--none); }
.s-error { background: var(--err-soft); color: var(--err); }
.list { display: flex; flex-wrap: wrap; gap: 4px; max-width: 340px; }
.list code { background: var(--bg); border-radius: 4px; padding: 1px 5px; }
.size { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }
.more { border: 0; background: none; color: var(--accent); font-size: 12px; padding: 0; }
.missing, .absent { color: var(--muted); font-size: 12.5px; }
.counts, .downloads { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.pill { border: 1px solid transparent; border-radius: 99px; padding: 3px 11px; font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; background: var(--none-soft); color: var(--none); }
.pill[aria-pressed="true"] { border-color: currentColor; }
.pill.s-resolved { background: var(--ok-soft); color: var(--ok); }
.pill.s-review { background: var(--warn-soft); color: var(--warn); }
.pill.s-error { background: var(--err-soft); color: var(--err); }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 14px; align-items: start; }
.layout.single { grid-template-columns: minmax(0, 1fr); }
@media (max-width: 900px) { .layout { grid-template-columns: minmax(0, 1fr); } }
.side { display: grid; gap: 14px; min-width: 0; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; display: grid; gap: 10px; min-width: 0; }
.card h3 { font-size: 15px; }
.route { display: grid; }
.hop { display: grid; grid-template-columns: 14px minmax(0, 1fr); gap: 10px; font-size: 13px; }
.hop .rail { display: flex; flex-direction: column; align-items: center; }
.hop .dot { width: 10px; height: 10px; border-radius: 99px; background: var(--accent); margin-top: 5px; flex: none; }
.hop .stem { width: 2px; background: var(--line); flex: 1; min-height: 14px; }
.hop .what { padding-bottom: 12px; display: grid; gap: 2px; min-width: 0; }
.hop .src { font-weight: 600; }
.hop .io { font-family: var(--mono); font-size: 12px; overflow-wrap: anywhere; }
.hop .tally { color: var(--muted); font-size: 12.5px; }
.hop .tally .bad { color: var(--err); }
.routelink { color: var(--accent); font-size: 13px; text-decoration: none; }
.routelink:hover { text-decoration: underline; }
.cite { font-size: 12.5px; display: grid; gap: 2px; border-top: 1px solid var(--line); padding-top: 8px; }
.cite:first-of-type { border-top: 0; padding-top: 0; }
.cite a { color: var(--accent); word-break: break-all; }
.lic { font-family: var(--mono); font-size: 11.5px; color: var(--muted); }
tr.review-row td { background: var(--warn-soft); }
.review { display: grid; gap: 6px; }
.cand { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 13px; }
.cand .conf { font-family: var(--mono); font-size: 12px; color: var(--muted); }
.choose { border: 1px solid var(--warn); background: var(--panel); color: var(--warn); border-radius: 6px; padding: 2px 10px; font-size: 12.5px; }
.choose[aria-pressed="true"] { background: var(--warn); color: var(--panel); }
.resumebar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--warn-soft); border-radius: 8px; font-size: 13.5px; }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="brand">Braidworks</div>
    <nav class="nav"><a href="/" aria-current="page">Look up</a><a href="/explore">Explore sources</a></nav>
  </header>

  <div class="intro">
    <h1>Look up what you need for a list of IDs</h1>
    <p>Paste identifiers, say what they are, and pick the fields you want. Braidworks finds a route across the installed sources and returns one row per ID.</p>
  </div>

  <div class="form">
    <section class="step" aria-labelledby="s1">
      <div class="step-head"><span class="num">1</span><h2 id="s1">Your IDs</h2><span class="hint">One per line, or separated by spaces or commas.</span></div>
      <textarea id="ids" spellcheck="false" aria-label="Identifiers" placeholder="P04637&#10;BRCA1"></textarea>
      <div class="row">
        <span class="count" id="idcount"></span>
        <label class="ghost" for="file">Upload a list or table…</label>
        <input type="file" id="file" accept=".txt,.csv,.tsv,text/plain,text/csv,text/tab-separated-values" hidden>
        <span class="hint" id="tablenote" hidden></span>
        <button class="ghost" id="cleartable" type="button" hidden>Use pasted IDs instead</button>
      </div>
    </section>

    <section class="step" aria-labelledby="s2" id="step-type">
      <div class="step-head"><span class="num">2</span><h2 id="s2">What are they?</h2><span class="hint">Braidworks does not guess: the type decides the route.</span></div>
      <div class="types" id="types" role="radiogroup" aria-labelledby="s2"></div>
      <label class="row hint" for="moretypes">Another input type <select id="moretypes"></select></label>
    </section>

    <section class="step" aria-labelledby="s3">
      <div class="step-head"><span class="num">3</span><h2 id="s3">What do you want?</h2><span class="hint">Search in plain words; tick the fields to return.</span></div>
      <input type="search" class="search" id="q" placeholder="e.g. pdb structures, pathways, protein name" aria-label="Search fields">
      <div class="chosen" id="chosen" aria-live="polite"></div>
      <div class="matches" id="matches"></div>
      <div id="routebox" hidden>
        <h3 class="hint" id="optionshead" hidden>Options for this route</h3>
        <div class="problem" id="problem"></div>
        <div class="options" id="options"></div>
      </div>
    </section>

    <div class="runbar">
      <span class="progress" id="progress" aria-live="polite">Paste IDs, choose their type and at least one field.</span>
      <button class="run" id="run" type="button" disabled>Get fields</button>
    </div>
  </div>

  <section class="results" id="results" hidden aria-live="polite">
    <div class="rhead">
      <h2>Results</h2>
      <div class="counts" id="counts"></div>
      <div class="downloads" aria-label="Download">
        <button class="ghost" type="button" data-export="csv">CSV</button>
        <button class="ghost" type="button" data-export="tsv">TSV</button>
        <button class="ghost" type="button" data-export="json">JSON</button>
      </div>
    </div>
    <div class="resumebar" id="resumebar" hidden>
      <span id="resumetext"></span>
      <button class="run" id="resume" type="button">Resume</button>
    </div>
    <div class="layout">
      <div class="tablebox"><table id="table"></table></div>
      <aside class="side">
        <section class="card" id="routecard" hidden>
          <h3>How this was answered</h3>
          <div class="route" id="route"></div>
          <a class="routelink" href="/explore">See these sources on the network →</a>
        </section>
        <section class="card" id="citecard" hidden>
          <h3>Sources to cite</h3>
          <div id="cites"></div>
        </section>
      </aside>
    </div>
  </section>
</div>

<script>
const CATALOG = __CATALOG__;
const STARTS = __STARTS__;

const FIELDS = CATALOG.map(([type_id, description, sources, inputs, consumers]) => ({ type_id, description, sources, inputs, consumers }));
const BY_ID = Object.fromEntries(FIELDS.map(f => [f.type_id, f]));
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const state = { have: STARTS[0] || "", want: [], table: null, params: {}, paramCaps: [], routeOk: false, matches: [], running: false, filter: null, decisions: {}, token: null, exports: null };

// A field is reachable when some capability producing it starts from something reachable.
function reachable(start) {
  const seen = new Set([start]); let grew = true;
  while (grew) { grew = false; for (const f of FIELDS) if (!seen.has(f.type_id) && f.inputs.some(i => seen.has(i))) { seen.add(f.type_id); grew = true; } }
  return seen;
}
function ids() { return $("#ids").value.split(/[\s,;]+/).map(s => s.trim()).filter(Boolean); }

function renderCount() {
  if (state.table) { $("#idcount").innerHTML = `<b>${state.table.rows}</b> table row${state.table.rows === 1 ? "" : "s"}`; return; }
  const list = ids(), dup = list.length - new Set(list).size;
  $("#idcount").innerHTML = `<b>${list.length}</b> ID${list.length === 1 ? "" : "s"}` + (dup ? ` · ${dup} repeated (each keeps its own row)` : "");
}
function renderTypes() {
  $("#step-type").hidden = !!state.table;
  $("#types").innerHTML = STARTS.map(t => `<button type="button" class="type" role="radio" aria-checked="${state.have === t}" data-type="${esc(t)}"><span class="tid">${esc(t)}</span><span class="desc">${esc((BY_ID[t] || {}).description || "")}</span></button>`).join("");
  const others = FIELDS.filter(f => f.consumers > 0 && !STARTS.includes(f.type_id)).sort((a, b) => b.consumers - a.consumers || a.type_id.localeCompare(b.type_id));
  $("#moretypes").innerHTML = `<option value="">Choose…</option>` + others.map(f => `<option value="${esc(f.type_id)}" ${state.have === f.type_id ? "selected" : ""}>${esc(f.type_id)}</option>`).join("");
}
function startTypes() { return state.table ? state.table.columns : [state.have]; }
function renderMatches() {
  const reach = new Set(); for (const t of startTypes()) for (const r of reachable(t)) reach.add(r);
  const starts = new Set(startTypes());
  $("#matches").hidden = !$("#q").value.trim();
  $("#matches").innerHTML = state.matches.length ? state.matches.map(f => {
    const ok = reach.has(f.type_id) && !starts.has(f.type_id), on = state.want.includes(f.type_id);
    const from = f.inputs.length ? `from ${f.inputs.slice(0, 3).join(", ")}${f.inputs.length > 3 ? "…" : ""}` : "an input you supply";
    return `<label class="match${ok ? "" : " off"}" for="f-${esc(f.type_id)}">
      <input type="checkbox" id="f-${esc(f.type_id)}" data-field="${esc(f.type_id)}" ${on ? "checked" : ""} ${ok ? "" : "disabled"}>
      <span><span class="tid">${esc(f.type_id)}</span> — ${esc(f.description || "(no description)")}</span>
      <span class="meta">${esc(f.sources.join(", "))} · ${esc(from)}${ok ? "" : ` · <span class="noroute">no route from ${esc([...starts].join(", "))}</span>`}</span></label>`;
  }).join("") : `<div class="match"><span></span><span class="meta">No field matches. Try other words, or browse every field under Explore sources.</span></div>`;
  $("#chosen").innerHTML = state.want.length ? state.want.map(t => `<span class="chip">${esc(t)}<button type="button" aria-label="Remove ${esc(t)}" data-remove="${esc(t)}">×</button></span>`).join("") : `<span class="hint">No fields chosen yet.</span>`;
}

let findTimer = null, findSeq = 0;
function search() {
  clearTimeout(findTimer);
  findTimer = setTimeout(async () => {
    const q = $("#q").value.trim(), seq = ++findSeq;
    if (!q) { state.matches = []; renderMatches(); return; }
    try {
      const r = await (await fetch(`/api/find?q=${encodeURIComponent(q)}&limit=8`)).json();
      if (seq !== findSeq) return;
      state.matches = r.ok ? r.matches : [];
    } catch { state.matches = []; }
    renderMatches();
  }, 180);
}

// Plan the route whenever the inputs or fields change: shows the route's own options
// (e.g. a species filter) and explains a missing route before anything runs.
let planSeq = 0;
async function plan() {
  const seq = ++planSeq;
  state.routeOk = false; state.paramCaps = [];
  if (!state.want.length || !startTypes().length) { $("#routebox").hidden = true; renderRun(); return; }
  try {
    const r = await (await fetch("/api/plan", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ from_types: startTypes(), to_types: state.want }) })).json();
    if (seq !== planSeq) return;
    state.routeOk = !!r.ok;
    state.paramCaps = r.ok ? (r.parameter_capabilities || []) : [];
    $("#problem").textContent = r.ok ? "" : r.error;
  } catch (e) { $("#problem").textContent = "Could not reach the server: " + e.message; }
  renderOptions(); renderRun();
}
function renderOptions() {
  const fields = [];
  for (const cap of state.paramCaps) for (const p of cap.parameters) {
    const id = `p-${cap.capability}-${p.name}`, value = (state.params[cap.capability] || {})[p.name] ?? "";
    const control = p.enum && p.enum.length ? `<select id="${esc(id)}" data-cap="${esc(cap.capability)}" data-param="${esc(p.name)}"><option value="">Default${p.default !== null && p.default !== undefined ? ` (${esc(p.default)})` : ""}</option>${p.enum.map(v => `<option ${String(value) === String(v) ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>`
      : `<input type="text" id="${esc(id)}" data-cap="${esc(cap.capability)}" data-param="${esc(p.name)}" value="${esc(value)}" placeholder="${p.default !== null && p.default !== undefined ? "default " + esc(p.default) : "optional"}">`;
    fields.push(`<label for="${esc(id)}">${esc(p.name)} <span class="note">${esc(cap.weaver)} · ${esc(cap.capability)}</span>${control}<span class="note">${esc(p.description || "")}</span></label>`);
  }
  $("#options").innerHTML = fields.join("");
  $("#optionshead").hidden = !fields.length;
  $("#routebox").hidden = !fields.length && !$("#problem").textContent;
}
function renderRun() {
  const n = state.table ? state.table.rows : ids().length, k = state.want.length;
  const btn = $("#run");
  btn.textContent = state.running ? "Running…" : k && n ? `Get ${k} field${k === 1 ? "" : "s"} for ${n} ${state.table ? "row" : "ID"}${n === 1 ? "" : "s"}` : "Get fields";
  btn.disabled = state.running || !(k && n && state.routeOk);
  if (!state.running && !state.result && !state.failed) $("#progress").textContent = !n ? "Paste IDs to start." : !k ? "Pick at least one field to return." : state.routeOk ? "Ready." : "Checking the route…";
}

function sizeText(s) { return s.complete ? `${s.shown}` : s.total === null ? `${s.shown}+` : `${s.shown} of ${s.total}`; }
function cell(value, size, key) {
  if (value === null || value === undefined) return `<td class="absent">—</td>`;
  if (Array.isArray(value)) {
    const shown = value.slice(0, 3).map(x => `<code>${esc(x)}</code>`).join(""), rest = value.length - 3;
    const count = size ? sizeText(size) : String(value.length);
    return `<td><div class="list" data-list="${esc(key)}">${shown}${rest > 0 ? `<button type="button" class="more" data-more="${esc(key)}">+${rest} more</button>` : ""}</div><span class="size">${count} in total</span></td>`;
  }
  if (typeof value === "object") return `<td><code>${esc(JSON.stringify(value))}</code></td>`;
  return `<td>${esc(value)}</td>`;
}
const STATUS_LABELS = { resolved: "resolved", review: "need review", unresolved: "unresolved", error: "errors" };
function reviewFor(table, row) { return (table.review || []).find(item => item.input === row.input && item.row === row.row); }
function reviewCells(item, span) {
  const chosen = state.decisions[item.key];
  const pressed = (action, index) => chosen && chosen.action === action && (index === undefined || chosen.candidate_index === index);
  const cands = item.candidates.map(c => `<div class="cand"><button type="button" class="choose" aria-pressed="${pressed("select", c.index)}" data-key="${esc(item.key)}" data-action="select" data-index="${c.index}">Choose</button>${Object.entries(c.values).map(([t, v]) => `<code>${esc(t)}</code> ${esc(Array.isArray(v) ? v.join("; ") : v)}`).join(" · ")} <span class="conf">confidence ${Number(c.confidence).toFixed(2)}</span></div>`).join("");
  const accept = item.ambiguous ? "" : `<button type="button" class="choose" aria-pressed="${pressed("accept")}" data-key="${esc(item.key)}" data-action="accept">Accept</button>`;
  const why = item.ambiguous ? `${esc(item.step)} found ${item.candidates.length} possible matches. Choose one, or reject the row.` : `${esc(item.step)} flagged this match for a check. Accept it, or reject the row.`;
  const notes = item.warnings.length ? `<span class="hint">${item.warnings.map(esc).join(" · ")}</span>` : "";
  return `<td colspan="${span}"><div class="review"><span>${why}</span>${notes}${cands}<div class="cand">${accept}<button type="button" class="choose" aria-pressed="${pressed("reject")}" data-key="${esc(item.key)}" data-action="reject">Reject</button></div></div></td>`;
}
function renderResults(table) {
  state.result = table;
  $("#results").hidden = false;
  const counts = { resolved: 0, review: 0, unresolved: 0, error: 0 };
  table.rows.forEach(row => { counts[row.status] = (counts[row.status] || 0) + 1; });
  $("#counts").innerHTML = `<span class="pill">${table.rows.length} rows</span>` + Object.entries(STATUS_LABELS).map(([status, label]) =>
    `<button type="button" class="pill s-${status}" aria-pressed="${state.filter === status}" data-filter="${status}">${counts[status] || 0} ${label}</button>`).join("");
  const parent = table.columns.includes("parent");
  const head = `<thead><tr><th>Input</th>${parent ? "<th>From</th>" : ""}<th>Status</th>${table.want.map(t => `<th><code>${esc(t)}</code></th>`).join("")}<th>Missing</th></tr></thead>`;
  const body = table.rows.map((row, i) => {
    if (state.filter && row.status !== state.filter) return "";
    const lead = `<td class="input">${esc(row.input)}</td>${parent ? `<td class="mono">${esc(row.parent || "")}</td>` : ""}<td><span class="status s-${esc(row.status)}">${esc(row.status)}</span></td>`;
    const item = row.status === "review" ? reviewFor(table, row) : null;
    if (item) return `<tr class="review-row">${lead}${reviewCells(item, table.want.length + 1)}</tr>`;
    return `<tr>${lead}${table.want.map(t => cell(row[t], (table.sizes[i] || {})[t], i + ":" + t)).join("")}<td class="missing">${esc((row.missing || []).join(", "))}</td></tr>`;
  }).join("");
  $("#table").innerHTML = head + `<tbody>${body}</tbody>`;
  const refs = table.references || [];
  $("#citecard").hidden = !refs.length;
  $("#results .layout").classList.toggle("single", !refs.length && $("#routecard").hidden);
  $("#cites").innerHTML = refs.map(r => `<div class="cite"><b>${esc(r.attribution || r.weaver_id)}</b>${r.license ? `<span class="lic">${esc(r.license)}</span>` : ""}${r.citation ? (/^https?:/.test(r.citation) ? `<a href="${esc(r.citation)}" target="_blank" rel="noopener">${esc(r.citation)}</a>` : `<span>${esc(r.citation)}</span>`) : ""}${r.source_url ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source_url)}</a>` : ""}</div>`).join("");
  renderResume();
}
// The steps that ran, in order, with what each did across the final rows.
function tally(counts) {
  if (!counts) return "did not run for these rows";
  const parts = [], st = counts.statuses || {};
  if (st.ok) parts.push(`${st.ok} found`);
  if (st.no_match) parts.push(`${st.no_match} no match`);
  if (st.skipped) parts.push(`${st.skipped} skipped (no input)`);
  if (counts.errors) parts.push(`<span class="bad">${counts.errors} failed</span>`);
  if (counts.recovered) parts.push(`${counts.recovered} rerouted after a failure`);
  const via = Object.keys(counts.backends || {});
  return (via.length ? `via ${via.map(esc).join(", ")} · ` : "") + (parts.join(" · ") || "no rows reached this step");
}
function hop(source, capability, io, counts, params, last) {
  const opts = Object.entries(params || {}).map(([k, v]) => `${esc(k)} = ${esc(v)}`).join(", ");
  return `<div class="hop"><div class="rail"><span class="dot"></span>${last ? "" : `<span class="stem"></span>`}</div><div class="what"><span><span class="src">${esc(source)}</span> <code>${esc(capability)}</code></span>${io ? `<span class="io">${io}</span>` : ""}<span class="tally">${tally(counts)}</span>${opts ? `<span class="tally">options: ${opts}</span>` : ""}</div></div>`;
}
function renderRoute(done) {
  const outcomes = done.step_outcomes || {}, params = done.effective_params || {};
  const routes = done.planned_routes || [], blocks = [];
  routes.forEach((route, n) => {
    const head = routes.length > 1 ? `<span class="hint">Rows starting from ${esc(route.from_types.join(", "))}</span>` : "";
    blocks.push(head + route.steps.map((step, i) => hop(step.weaver_id, step.capability_id,
      `${step.input_types.map(esc).join(", ")} → ${step.output_types.map(esc).join(", ")}`,
      outcomes[step.capability_id], params[step.capability_id], i === route.steps.length - 1)).join(""));
  });
  if (!routes.length && (done.traverse || []).length) {
    blocks.push(done.traverse.map((cid, i) => hop("for each", cid, "", outcomes[cid], params[cid], i === done.traverse.length - 1)).join(""));
  }
  $("#routecard").hidden = !blocks.length;
  $("#route").innerHTML = blocks.join("");
}
function renderResume() {
  const paused = (state.result && state.result.review || []).length, decided = Object.keys(state.decisions).length;
  $("#resumebar").hidden = !paused;
  $("#resumetext").textContent = decided ? `${decided} of ${paused} paused row${paused === 1 ? "" : "s"} decided. Resume to finish ${decided === 1 ? "it" : "them"}; undecided rows stay paused.` : `${paused} row${paused === 1 ? "" : "s"} paused for your choice.`;
  $("#resume").disabled = !decided || state.running;
}
function download(kind) {
  const text = state.exports && state.exports[kind]; if (!text) return;
  const type = { csv: "text/csv", tsv: "text/tab-separated-values", json: "application/json" }[kind];
  const url = URL.createObjectURL(new Blob([text], { type: type + ";charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `braidworks-results.${kind}` });
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function showOutcome(done) {
  state.exports = done.exports; state.token = done.review_token || null; state.decisions = {};
  renderRoute(done);
  renderResults(done.table);
  $("#progress").textContent = done.table.summary;
}
async function resume() {
  state.running = true; renderRun(); renderResume();
  const progress = $("#progress"); progress.classList.remove("error"); progress.textContent = "Resuming the paused rows…";
  try {
    if (!state.token) throw new Error("this result has no paused rows to resume");
    const decisions = Object.values(state.decisions).map(d => ({ version: 1, entity_key: d.key, action: d.action, candidate_index: d.candidate_index ?? null }));
    const r = await (await fetch("/api/review", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ token: state.token, decisions }) })).json();
    if (!r.ok) throw new Error(r.error);
    showOutcome(r);
  } catch (e) { state.failed = true; progress.classList.add("error"); progress.textContent = "Resume failed: " + e.message; }
  finally { state.running = false; renderRun(); renderResume(); }
}

function requestBody() {
  const params = {};
  for (const [cap, values] of Object.entries(state.params)) {
    const kept = Object.fromEntries(Object.entries(values).filter(([, v]) => String(v).trim() !== ""));
    if (Object.keys(kept).length) params[cap] = kept;
  }
  const batch = state.table ? { text: state.table.text, format: state.table.format }
    : { text: ids().join("\n"), format: "lines", input_type: state.have };
  return { have: {}, want: state.want, batch, params };
}
async function run() {
  state.running = true; state.result = null; state.failed = false; renderRun();
  const progress = $("#progress"); progress.classList.remove("error"); progress.textContent = "Planning and starting…";
  try {
    const response = await fetch("/api/run/stream", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(requestBody()) });
    if (!response.ok) throw new Error(`the server rejected the request (${response.status})`);
    const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = "", done = null;
    while (!done) {
      const chunk = await reader.read();
      buffer = (buffer + decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done })).replace(/\r\n/g, "\n");
      let at;
      while ((at = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, at); buffer = buffer.slice(at + 2);
        const data = frame.split("\n").filter(l => l.startsWith("data:")).map(l => l.slice(5).trim()).join("\n");
        if (!data) continue;
        const event = JSON.parse(data);
        if (event.event === "wave" && event.input_count) progress.textContent = `Looked up ${event.completed_inputs} of ${event.input_count} input${event.input_count === 1 ? "" : "s"}…`;
        else if (event.event === "error") throw new Error(event.error);
        else if (event.event === "done") done = event;
      }
      if (chunk.done && !done) throw new Error("the run ended without a result");
    }
    if (!done.ok) throw new Error(done.error || "the run failed");
    state.filter = null;
    showOutcome(done);
  } catch (e) {
    state.failed = true; progress.classList.add("error"); progress.textContent = "Run failed: " + e.message;
  } finally { state.running = false; renderRun(); }
}

// ---- events ----
$("#ids").addEventListener("input", () => { renderCount(); renderRun(); });
$("#types").addEventListener("click", e => { const b = e.target.closest("[data-type]"); if (!b) return; state.have = b.dataset.type; renderTypes(); renderMatches(); plan(); });
$("#moretypes").addEventListener("change", e => { if (!e.target.value) return; state.have = e.target.value; renderTypes(); renderMatches(); plan(); });
$("#q").addEventListener("input", search);
$("#matches").addEventListener("change", e => { const t = e.target.dataset.field; if (!t) return; state.want = e.target.checked ? [...state.want, t] : state.want.filter(x => x !== t); renderMatches(); plan(); });
$("#chosen").addEventListener("click", e => { const t = e.target.dataset.remove; if (!t) return; state.want = state.want.filter(x => x !== t); renderMatches(); plan(); });
$("#options").addEventListener("input", e => { const c = e.target.dataset.cap; if (!c) return; (state.params[c] ||= {})[e.target.dataset.param] = e.target.value; });
$("#run").addEventListener("click", run);
$("#resume").addEventListener("click", resume);
$("#results").addEventListener("click", e => {
  const f = e.target.closest("[data-filter]");
  if (f) { state.filter = state.filter === f.dataset.filter ? null : f.dataset.filter; renderResults(state.result); return; }
  const x = e.target.closest("[data-export]"); if (x) { download(x.dataset.export); return; }
  const d = e.target.closest("[data-action]");
  if (d) {
    const decision = { key: d.dataset.key, action: d.dataset.action, candidate_index: d.dataset.index !== undefined ? Number(d.dataset.index) : null };
    const same = state.decisions[decision.key];
    if (same && same.action === decision.action && same.candidate_index === decision.candidate_index) delete state.decisions[decision.key];
    else state.decisions[decision.key] = decision;
    renderResults(state.result); return;
  }
  const m = e.target.closest("[data-more]"); if (!m) return;
  const [i, t] = m.dataset.more.split(/:(.+)/), value = state.result.rows[Number(i)][t];
  m.parentElement.innerHTML = value.map(x => `<code>${esc(x)}</code>`).join("");
});
$("#file").addEventListener("change", async e => {
  const file = e.target.files[0]; if (!file) return;
  const text = await file.text(), name = file.name.toLowerCase();
  if (name.endsWith(".csv") || name.endsWith(".tsv")) {
    const sep = name.endsWith(".csv") ? "," : "\t", lines = text.split(/\r?\n/).filter(l => l.trim());
    const columns = (lines[0] || "").split(sep).map(c => c.trim()).filter(Boolean);
    state.table = { text, format: name.endsWith(".csv") ? "csv" : "tsv", columns, rows: Math.max(0, lines.length - 1) };
    $("#tablenote").textContent = `${file.name}: each column's header names its field (${columns.join(", ")}).`;
    $("#tablenote").hidden = $("#cleartable").hidden = false; $("#ids").disabled = true;
  } else { $("#ids").value = text; }
  e.target.value = ""; renderCount(); renderTypes(); renderMatches(); plan();
});
$("#cleartable").addEventListener("click", () => { state.table = null; $("#tablenote").hidden = $("#cleartable").hidden = true; $("#ids").disabled = false; renderCount(); renderTypes(); renderMatches(); plan(); });

renderTypes(); renderMatches(); renderCount(); renderRun();
</script>
</body>
</html>
"""


def page_data(registry: BraidRegistry) -> tuple[list, list[str]]:
    """The field catalogue as compact rows, and the types queries usually start from."""
    catalog = field_catalog(registry)
    rows = [
        [info.type_id, info.description, list(info.sources), list(info.inputs), info.consumers]
        for info in catalog.values()
    ]
    produced = {type_id for type_id, info in catalog.items() if info.inputs}
    # Most widely accepted first: the first card is the default choice.
    starts = sorted(
        (t for t, info in catalog.items() if info.consumers and t not in produced),
        key=lambda t: (-catalog[t].consumers, t),
    )
    return rows, starts


def _script_json(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_lookup_page(registry: BraidRegistry) -> str:
    """The landing page with this registry's fields and start types injected."""
    rows, starts = page_data(registry)
    return PAGE.replace("__CATALOG__", _script_json(rows)).replace(
        "__STARTS__", _script_json(starts)
    )
