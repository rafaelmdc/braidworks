"""The interactive (``weaverkit serve``-only) UI, split out of the static template.

``_view_template.py`` is the self-contained *static* network picture. The builder / run /
results controls are only meaningful when served (they call ``/api/plan`` and
``/api/run``), so they live here and are injected into the page **only when serving**
(``render_html(..., interactive=True)``). A ``file://`` export of ``weaverkit view`` carries
none of this — it stays lean.

Layout (kept deliberately uncluttered): a compact **Build** dock (top-left) for the
plan/run form, and full-screen **sheets** (modal pages) for the heavier output — generated
code, citations, and the results table — so they never overlap the graph or balloon. The
graph itself is the page; the dock drives it; sheets are summoned on demand.

Three fragments, slotted into the template's ``__SERVE_CSS__`` / ``__SERVE_HTML__`` /
``__SERVE_JS__`` markers. The JS runs in the template's ``<script>`` scope, so it freely
references the base globals (``DATA``, ``VIEWS``, ``layouts``, ``particles``,
``computeLayout``, ``selectView``, ``esc``) and the base light-up / search state
(``runAnim`` / ``searchHits`` — written here, read by the draw loop).
"""

from __future__ import annotations

SERVE_CSS = """
  /* --- Build dock (top-left) --- */
  .builder {
    position: fixed; top: 80px; left: 18px; z-index: 12; width: 304px;
    max-height: calc(100vh - 112px); overflow-y: auto;
    background: var(--panel); backdrop-filter: blur(14px);
    border: 1px solid var(--panel-edge); border-radius: 14px;
    padding: 16px; font-size: 12.5px;
    box-shadow: 0 22px 54px rgba(0,0,0,0.42);
  }
  .builder h2 {
    font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-dim); margin: 0 0 12px;
  }
  .bgroup { margin-bottom: 11px; }
  .blabel { display: block; color: var(--ink-dim); font-size: 10px; text-transform: uppercase;
    letter-spacing: 0.07em; margin-bottom: 4px; }
  .builder input, .builder select {
    width: 100%; box-sizing: border-box; background: rgba(10,16,30,0.6); color: var(--ink);
    border: 1px solid var(--panel-edge); border-radius: 8px; padding: 8px 10px; font-size: 12.5px;
  }
  .builder input:focus, .builder select:focus { outline: none; border-color: rgba(120,150,220,0.55); }
  .brow { display: flex; gap: 8px; align-items: center; }
  .brow .grow { flex: 1; }
  .btn { cursor: pointer; border-radius: 8px; padding: 8px 14px; font-size: 12.5px;
    border: 1px solid var(--panel-edge); background: transparent; color: var(--ink);
    white-space: nowrap; }
  .btn:hover { border-color: rgba(120,150,220,0.45); }
  .btn.primary { background: rgba(120,150,220,0.22); border-color: rgba(120,150,220,0.5); }
  .btn.primary:hover { background: rgba(120,150,220,0.34); }
  .btn.ghost { color: var(--ink-dim); padding: 6px 11px; font-size: 11px; }
  .btn.ghost:hover { color: var(--ink); }
  .btn:disabled { opacity: 0.5; cursor: default; }
  .bdiv { border-top: 1px solid var(--panel-edge); margin: 14px 0 12px; }
  .note { color: var(--ink-dim); font-size: 10.5px; line-height: 1.4; }
  .berr { color: #e6a3a3; font-size: 11.5px; line-height: 1.45; }
  /* post-plan summary + actions */
  .summary { background: rgba(120,150,220,0.09); border: 1px solid var(--panel-edge);
    border-radius: 10px; padding: 10px 12px; margin: 4px 0 12px; }
  .summary .route { color: var(--ink); font-size: 12.5px; line-height: 1.4; word-break: break-word; }
  .summary .steps { color: var(--ink-dim); font-size: 10.5px; margin-top: 3px; }
  .bactions { display: flex; gap: 7px; flex-wrap: wrap; margin-top: 11px; }

  /* --- Sheets (modal pages: code / citations / results) --- */
  .sheet-backdrop { position: fixed; inset: 0; z-index: 30; background: rgba(4,7,14,0.62);
    backdrop-filter: blur(3px); display: flex; align-items: center; justify-content: center; }
  .sheet-backdrop[hidden] { display: none; }
  .sheet { width: min(92vw, 980px); max-height: 85vh; display: flex; flex-direction: column;
    background: var(--panel); border: 1px solid var(--panel-edge); border-radius: 16px;
    box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
  .sheet-head { display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    border-bottom: 1px solid var(--panel-edge); }
  .sheet-head h3 { margin: 0; flex: 1; font-size: 12px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--ink); }
  .sheet-x { cursor: pointer; background: transparent; border: 1px solid var(--panel-edge);
    border-radius: 8px; color: var(--ink-dim); font-size: 15px; line-height: 1; padding: 3px 9px; }
  .sheet-x:hover { color: var(--ink); }
  .sheet-body { padding: 16px 18px; overflow: auto; }
  .sheet-body pre { background: rgba(8,12,24,0.7); border: 1px solid var(--panel-edge);
    border-radius: 8px; padding: 11px; font-size: 11px; line-height: 1.45; overflow-x: auto;
    white-space: pre-wrap; word-break: break-word; margin: 0; }
  .tabs { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
  .tab { cursor: pointer; font-size: 11px; color: var(--ink-dim);
    border: 1px solid var(--panel-edge); border-radius: 8px; padding: 5px 11px; }
  .tab.on { color: var(--ink); border-color: rgba(120,150,220,0.5); background: rgba(120,150,220,0.12); }
  .copyrow { display: flex; justify-content: flex-end; margin-bottom: 6px; }
  .rcounts { color: var(--ink-dim); font-size: 11px; margin-bottom: 12px; }
  .rtable { border-collapse: collapse; width: 100%; font-size: 12px; }
  .rtable th, .rtable td { text-align: left; padding: 7px 10px;
    border-bottom: 1px solid var(--panel-edge); white-space: nowrap; max-width: 360px;
    overflow: hidden; text-overflow: ellipsis; }
  .rtable th { position: sticky; top: -16px; background: var(--panel); color: var(--ink-dim);
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; }
  .rtable td { color: var(--ink); }

  /* --- click-to-build mode --- */
  .chips { display: flex; flex-wrap: wrap; gap: 5px; min-height: 22px; align-items: center; }
  .chip-sel { display: inline-flex; align-items: center; gap: 6px; font-size: 11px;
    border-radius: 7px; padding: 3px 8px; border: 1px solid var(--panel-edge); color: var(--ink); }
  .chip-have { background: rgba(95,208,160,0.16); border-color: rgba(95,208,160,0.55); }
  .chip-through { background: rgba(232,192,105,0.16); border-color: rgba(232,192,105,0.55); }
  .chip-want { background: rgba(111,155,255,0.16); border-color: rgba(111,155,255,0.55); }
  .chip-sel .x { cursor: pointer; color: var(--ink-dim); font-size: 12px; }
  .chip-sel .x:hover { color: var(--ink); }
  .bg-empty { color: var(--ink-dim); font-size: 10.5px; }
  .picker { position: fixed; z-index: 40; background: var(--panel); backdrop-filter: blur(14px);
    border: 1px solid var(--panel-edge); border-radius: 11px; padding: 6px; min-width: 210px;
    max-width: 320px; max-height: 56vh; overflow-y: auto; box-shadow: 0 22px 54px rgba(0,0,0,0.5); }
  .picker .pkhead { font-size: 10px; text-transform: uppercase; letter-spacing: 0.07em;
    color: var(--ink-dim); padding: 5px 9px 6px; }
  .picker .pk { display: block; width: 100%; box-sizing: border-box; text-align: left;
    cursor: pointer; background: transparent; border: 0; color: var(--ink); font-size: 12px;
    padding: 7px 9px; border-radius: 7px; }
  .picker .pk:hover { background: rgba(120,150,220,0.18); }
  .picker .pk.fan { color: #f0d18a; }
"""

SERVE_HTML = """
<div class="builder" id="builder" style="display:none">
  <h2>Build</h2>
  <div class="bgroup"><input id="b-search" placeholder="Filter graph" autocomplete="off"></div>

  <!-- Click-to-build: pick nodes on the graph instead of typing types. -->
  <div class="brow">
    <button class="btn primary grow" id="b-build">Build on the graph</button>
  </div>
  <div id="bg-panel" style="display:none; margin-top:11px">
    <div class="note" id="bg-hint"></div>
    <div class="bgroup" style="margin-top:9px">
      <span class="blabel">Have (start)</span><div id="bg-have" class="chips"></div>
    </div>
    <div class="bgroup">
      <span class="blabel">Pass through · for-each</span><div id="bg-through" class="chips"></div>
    </div>
    <div class="bgroup">
      <span class="blabel">Want</span><div id="bg-want" class="chips"></div>
    </div>
    <input id="bg-value" placeholder="value, e.g. TP53" autocomplete="off">
    <div class="brow" style="margin-top:8px">
      <button class="btn primary" id="bg-run">Run</button>
      <button class="btn ghost" id="bg-reset">Reset</button>
      <button class="btn ghost" id="bg-exit">Exit</button>
    </div>
  </div>

  <details style="margin-top:12px">
    <summary class="blabel" style="cursor:pointer">Type it instead (advanced)</summary>
    <div class="bgroup" style="margin-top:8px">
      <span class="blabel">Have</span>
      <input id="b-have" list="b-types" placeholder="protein.query" autocomplete="off">
    </div>
    <div class="bgroup">
      <span class="blabel">Want</span>
      <input id="b-want" list="b-types" placeholder="pdb.id" autocomplete="off">
    </div>
    <datalist id="b-types"></datalist>
    <div class="brow">
      <button class="btn primary" id="b-plan">Plan</button>
    </div>
    <div class="note" style="margin-top:8px">Comma-separate multiple types. Autocomplete from the network.</div>
  </details>

  <div class="bgroup" style="margin-top:11px">
    <span class="blabel">Backend</span>
    <select id="b-policy" title="backend policy">
      <option value="local_first">local first</option>
      <option value="api_first">api first</option>
      <option value="local_only">local only</option>
      <option value="api_only">api only</option>
    </select>
  </div>

  <div id="b-out"></div>

  <div class="bdiv"></div>
  <span class="blabel">Recipes</span>
  <select id="b-recipes"><option value="">load saved…</option></select>
  <div class="brow" style="margin-top:8px">
    <input id="b-recipe-name" class="grow" placeholder="name">
    <button class="btn" id="b-save">Save</button>
  </div>
</div>

<div class="sheet-backdrop" id="sheet" hidden>
  <div class="sheet">
    <div class="sheet-head"><h3 id="sheet-title"></h3><button class="sheet-x" id="sheet-x">&times;</button></div>
    <div class="sheet-body" id="sheet-body"></div>
  </div>
</div>
"""

SERVE_JS = r"""
// ---- builder (weaverkit serve only) ----------------------------------------
// Interactive only when served over HTTP; a file:// export stays the static picture.
const SERVED = location.protocol === "http:" || location.protocol === "https:";

let lastPlan = null;   // {from, to, policy, path} of the current built route
let lastDoc = null;    // the /api/plan response (artifacts + citations)
let lastRun = null;    // {columns, rows} for export

function newParticles(L) {
  return L.edges.map(() => Array.from({ length: 3 }, (_, i) => i / 3 + Math.random() * 0.04));
}

// Inject a planned route as a view (same shape as DATA.paths), reusing the path
// renderer. A single reusable "built" slot, so re-planning replaces rather than piles up.
function addPlanView(path) {
  const view = { key: "built", label: path.title, graph: path, path: path };
  let i = VIEWS.findIndex((v) => v.key === "built");
  if (i < 0) { i = VIEWS.length; VIEWS.push(view); } else { VIEWS[i] = view; }
  layouts[i] = computeLayout(path);
  particles[i] = newParticles(layouts[i]);
  selectView(i);
}

function splitTypes(s) {
  return (s || "").split(/[,\s]+/).map((t) => t.trim()).filter(Boolean);
}

function setHash(from, to) {
  location.hash = "have=" + encodeURIComponent(from.join(",")) +
    "&want=" + encodeURIComponent(to.join(","));
}

// ---- sheets (modal pages) --------------------------------------------------
function openSheet(title, html) {
  document.getElementById("sheet-title").textContent = title;
  document.getElementById("sheet-body").innerHTML = html;
  document.getElementById("sheet").hidden = false;
}
function closeSheet() { document.getElementById("sheet").hidden = true; }

// A copyable code/text block (copy button copies the following <pre>'s text).
function copyBlock(text) {
  return `<div class="copyrow"><button class="btn ghost copy">copy</button></div><pre>${esc(text)}</pre>`;
}
function wireCopies() {
  document.querySelectorAll("#sheet-body .copy").forEach((b) => {
    b.onclick = () => navigator.clipboard.writeText(b.parentElement.nextElementSibling.textContent);
  });
}

function showCode() {
  if (!lastDoc) return;
  const a = lastDoc.artifacts;
  const tabs = [
    ["weave", "Run (CLI)", a.cli_weave],
    ["path", "Route (CLI)", a.cli_path],
    ["python", "Python", a.python],
    ["json", "Braid JSON", JSON.stringify(a.braid, null, 2)],
  ];
  const head = `<div class="tabs">` +
    tabs.map((t, i) => `<span class="tab${i === 0 ? " on" : ""}" data-i="${i}">${esc(t[1])}</span>`).join("") +
    `</div>`;
  const panes = tabs.map((t, i) =>
    `<div class="pane" data-i="${i}" style="display:${i === 0 ? "block" : "none"}">${copyBlock(t[2])}</div>`
  ).join("");
  openSheet("Generated code", head + panes);
  wireCopies();
  document.querySelectorAll("#sheet-body .tab").forEach((tab) => {
    tab.onclick = () => {
      const i = tab.dataset.i;
      document.querySelectorAll("#sheet-body .tab").forEach((t) => t.classList.toggle("on", t === tab));
      document.querySelectorAll("#sheet-body .pane").forEach((p) => { p.style.display = p.dataset.i === i ? "block" : "none"; });
      wireCopies();
    };
  });
}

function showCite() {
  const cites = (lastDoc && lastDoc.citations) || [];
  const body = cites.length
    ? `<div class="note" style="margin-bottom:8px">Sources for this braid — copy into your methods / references.</div>`
      + copyBlock(cites.join("\n"))
    : `<div class="note">No source citations for this route.</div>`;
  openSheet("Citations", body);
  wireCopies();
}

// ---- run: execute the planned braid, light it up, tabulate ------------------
// runAnim + runStatusOf live in the base template (the draw loop reads them); we write
// runAnim here from a run result.
function startRunAnim(path, result) {
  const status = {};                                   // capability_id -> ok | error
  const scan = (leaves) => (leaves || []).forEach((l) =>
    (l.completion || []).forEach((o) => {
      const cur = status[o.capability_id];
      status[o.capability_id] =
        (o.status === "error" || cur === "error") ? "error"
        : (o.status === "ok" || cur === "ok") ? "ok" : (cur || o.status);
    }));
  scan(result.resolved);
  (result.unresolved || []).forEach((pair) => scan([pair[0]]));
  const waveOf = {};
  (path.waves || []).forEach((w, wi) => w.forEach((si) => { waveOf["op:" + si] = wi; }));
  const perNode = {};
  (path.nodes || []).forEach((n) => {
    if (n.kind === "op") perNode[n.id] = { wave: waveOf[n.id] || 0, status: status[n.capability] || "ok" };
  });
  runAnim = { start: performance.now(), perNode, waveMs: 650 };
}

function parseValues(types, raw) {
  raw = (raw || "").trim();
  if (types.length === 1) return raw ? { [types[0]]: raw } : {};
  const have = {};
  raw.split(",").forEach((pair) => {
    const i = pair.indexOf("=");
    if (i > 0) have[pair.slice(0, i).trim()] = pair.slice(i + 1).trim();
  });
  return have;
}

// The post-plan section of the dock: route summary, run controls, and links to the
// code / citations / results sheets. Kept compact — the heavy output lives in sheets.
function buildResultHTML(p) {
  const single = p.from_types.length === 1;
  const ph = single ? esc(p.from_types[0]) + " value" : esc(p.from_types.join("=")) + "=value, …";
  return `
    <div class="summary">
      <div class="route">${esc(p.from_types.join(", "))} &rarr; ${esc(p.to_types.join(", "))}</div>
      <div class="steps">${esc(String(p.step_count))} step(s)</div>
    </div>
    <span class="blabel">Run</span>
    <input id="r-values" placeholder="${ph}" autocomplete="off">
    <div class="brow" style="margin-top:8px">
      <button class="btn primary" id="r-run">Run</button>
      <select id="r-expand" class="grow" title="fan-out">
        <option value="top">top 1</option><option value="top_k">top k</option><option value="all">all</option>
      </select>
      <input id="r-k" type="number" min="1" value="3" style="width:48px" title="k">
    </div>
    <div class="bactions">
      <button class="btn ghost" id="b-code">Code</button>
      <button class="btn ghost" id="b-cite">Citations</button>
      <button class="btn ghost" id="b-results" style="display:none">Results</button>
    </div>`;
}

// Provisional live light-up: reveal the planned route wave-by-wave as SSE events arrive
// (statuses provisional "ok"; the final "done" event recolors via startRunAnim).
function initLiveAnim(path) {
  const waveOf = {};
  (path.waves || []).forEach((w, wi) => w.forEach((si) => { waveOf["op:" + si] = wi; }));
  const perNode = {};
  (path.nodes || []).forEach((n) => {
    if (n.kind === "op") perNode[n.id] = { wave: waveOf[n.id] || 0, status: "ok" };
  });
  runAnim = { live: true, revealedWave: -1, perNode, waveMs: 0 };
}

// Run via Server-Sent Events: the braid lights up live, wave by wave, as the executor's
// on_event fires server-side. The results open in the Results sheet.
function runBraid() {
  if (!lastPlan) return;
  const have = parseValues(lastPlan.from, document.getElementById("r-values").value);
  if (!Object.keys(have).length) return;
  const expand = document.getElementById("r-expand").value;
  const k = parseInt(document.getElementById("r-k").value, 10) || 3;
  const btn = document.getElementById("r-run"); btn.textContent = "running…"; btn.disabled = true;
  const done = () => { btn.textContent = "Run"; btn.disabled = false; };
  initLiveAnim(lastPlan.path);
  const qs = new URLSearchParams({
    have: JSON.stringify(have), want: lastPlan.to.join(","),
    policy: lastPlan.policy, expand, k: String(k),
  });
  const es = new EventSource("/api/run/stream?" + qs.toString());
  es.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.event === "wave") { runAnim.revealedWave = ev.wave; }
    else if (ev.event === "done") {
      es.close(); done();
      addPlanView(ev.path); startRunAnim(ev.path, ev.result); showResults(ev);
      const rb = document.getElementById("b-results");
      if (rb) { rb.style.display = ""; rb.onclick = () => showResults(); }
    } else if (ev.event === "error") { es.close(); done(); showError(ev.error); }
  };
  es.onerror = () => { es.close(); done(); };
}

function fmtCell(v) {
  if (v == null) return "";
  if (Array.isArray(v)) return v.join("; ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function showError(msg) {
  openSheet("Run failed", `<div class="berr">${esc(msg)}</div>`);
}

// Which columns to show: by default just the requested wants (the rest — intermediate
// join keys + the whole output group the weaver computed — are hidden behind the toggle).
let resultsShowAll = false;
function visibleCols() {
  if (!lastRun) return [];
  const { columns, want } = lastRun;
  if (resultsShowAll || !(want && want.length)) return columns;
  const shown = want.filter((c) => columns.includes(c));
  return shown.length ? shown : columns;   // fall back to all if none of the wants resolved
}
function toggleShowAll() { resultsShowAll = !resultsShowAll; showResults(); }

// Results as a modal page (never overlaps the graph; bounded + scrolls).
function showResults(d) {
  if (d) lastRun = { columns: d.columns, rows: d.rows, summary: d.summary, want: d.want || [] };
  if (!lastRun) return;
  const { rows, summary, want } = lastRun;
  const columns = visibleCols();
  const hidden = (lastRun.columns || []).length - columns.length;
  const s = summary || { resolved: rows.length, unresolved: 0, errors: 0 };
  let body = `<div class="rcounts">${s.resolved} resolved` +
    (s.unresolved ? `, ${s.unresolved} unresolved` : "") +
    (s.errors ? `, ${s.errors} error(s)` : "") + `</div>`;
  body += `<div class="bactions" style="margin:0 0 10px;align-items:center">` +
    `<button class="btn ghost" onclick="exportRows('csv')">Export CSV</button>` +
    `<button class="btn ghost" onclick="exportRows('tsv')">Export TSV</button>` +
    `<button class="btn ghost" onclick="exportRows('json')">Export JSON</button>`;
  if (want && want.length)
    body += `<label class="note" style="margin-left:auto;cursor:pointer;user-select:none">` +
      `<input type="checkbox" id="r-showall"${resultsShowAll ? " checked" : ""}> show all braid results` +
      (hidden > 0 ? ` (+${hidden} hidden)` : "") + `</label>`;
  body += `</div>`;
  if (!rows.length) {
    body += `<div class="note">No resolved rows.</div>`;
  } else {
    const th = columns.map((c) => `<th>${esc(c)}</th>`).join("");
    const trs = rows.map((row) =>
      "<tr>" + columns.map((c) => `<td title="${esc(fmtCell(row[c]))}">${esc(fmtCell(row[c]))}</td>`).join("") + "</tr>"
    ).join("");
    body += `<table class="rtable"><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table>`;
  }
  openSheet("Results", body);
  const cb = document.getElementById("r-showall");
  if (cb) cb.onchange = toggleShowAll;
}

function exportRows(fmt) {
  if (!lastRun) return;
  const { rows } = lastRun;
  const columns = visibleCols();
  let text, mime;
  if (fmt === "json") { text = JSON.stringify(rows, null, 2); mime = "application/json"; }
  else {
    const sep = fmt === "tsv" ? "\t" : ",";
    const q = (v) => { const s = fmtCell(v); return (fmt === "csv" && /[",\n]/.test(s)) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    text = [columns.join(sep), ...rows.map((r) => columns.map((c) => q(r[c])).join(sep))].join("\n");
    mime = fmt === "tsv" ? "text/tab-separated-values" : "text/csv";
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: mime }));
  a.download = "braidworks-results." + fmt;
  a.click(); URL.revokeObjectURL(a.href);
}

async function runPlan() {
  const out = document.getElementById("b-out");
  const from = splitTypes(document.getElementById("b-have").value);
  const to = splitTypes(document.getElementById("b-want").value);
  const policy = document.getElementById("b-policy").value;
  if (!from.length || !to.length) { out.innerHTML = `<div class="berr">Pick a Have and a Want type.</div>`; return; }
  out.innerHTML = `<div class="note">planning…</div>`;
  try {
    const r = await fetch("/api/plan", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ from_types: from, to_types: to, policy }),
    });
    const d = await r.json();
    if (!d.ok) { out.innerHTML = `<div class="berr"><b>No route.</b><br>${esc(d.error || "unroutable")}</div>`; return; }
    runAnim = null; lastRun = null;        // clear any prior run state when re-planning
    lastDoc = d;
    lastPlan = { from: d.path.from_types, to: d.path.to_types, policy, path: d.path };
    setHash(from, to);
    addPlanView(d.path);
    out.innerHTML = buildResultHTML(d.path);
    document.getElementById("r-run").onclick = runBraid;
    document.getElementById("r-values").addEventListener("keydown", (e) => { if (e.key === "Enter") runBraid(); });
    document.getElementById("b-code").onclick = showCode;
    document.getElementById("b-cite").onclick = showCite;
  } catch (e) { out.innerHTML = `<div class="berr">${esc(String(e))}</div>`; }
}

// ---- graph search (filter) -------------------------------------------------
// Sets the base template's `searchHits` (a Set of node ids to keep lit; null = no filter).
function applySearch(q) {
  q = (q || "").trim().toLowerCase();
  if (!q) { searchHits = null; return; }
  const hits = new Set();
  (layouts[current].nodes || new Map()).forEach((n) => {
    const hay = [n.label, n.key, n.weaver, n.capability].filter(Boolean).join(" ").toLowerCase();
    if (hay.includes(q)) hits.add(n.id);
  });
  searchHits = hits;
}

// ---- recipes (save/load built braids; client-side localStorage) ------------
const RECIPES_KEY = "braidworks.recipes";

function loadRecipes() {
  try { return JSON.parse(localStorage.getItem(RECIPES_KEY) || "{}"); }
  catch (e) { return {}; }
}

function refreshRecipes() {
  const sel = document.getElementById("b-recipes");
  if (!sel) return;
  const recipes = loadRecipes();
  sel.innerHTML = '<option value="">load saved…</option>' +
    Object.keys(recipes).sort().map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
}

function saveRecipe() {
  const name = (document.getElementById("b-recipe-name").value || "").trim();
  const have = document.getElementById("b-have").value.trim();
  const want = document.getElementById("b-want").value.trim();
  if (!name || (!have && !want)) return;
  const recipes = loadRecipes();
  recipes[name] = { have, want, policy: document.getElementById("b-policy").value };
  localStorage.setItem(RECIPES_KEY, JSON.stringify(recipes));
  document.getElementById("b-recipe-name").value = "";
  refreshRecipes();
  document.getElementById("b-recipes").value = name;
}

function loadRecipe(name) {
  const r = loadRecipes()[name];
  if (!r) return;
  document.getElementById("b-have").value = r.have || "";
  document.getElementById("b-want").value = r.want || "";
  if (r.policy) document.getElementById("b-policy").value = r.policy;
  runPlan();
}

// ---- click-to-build: pick have / pass-through / want on the graph ----------
// build.have/want hold type keys; build.through holds fan capability ids (--for-each).
const build = { have: [], through: [], want: [] };
let pickerEl = null;

function netNodeById(id) { return (DATA.network.nodes || []).find((n) => n.id === id); }

function buildChip(role, label, onRemove) {
  const c = document.createElement("span");
  c.className = "chip-sel chip-" + role;
  c.innerHTML = `<span>${esc(label)}</span><span class="x" title="remove">&times;</span>`;
  c.querySelector(".x").onclick = onRemove;
  return c;
}

function renderBuild() {
  const fill = (id, role, items, remove) => {
    const box = document.getElementById(id); if (!box) return;
    box.innerHTML = "";
    if (!items.length) { box.innerHTML = `<span class="bg-empty">— none —</span>`; return; }
    items.forEach((it, i) => box.appendChild(buildChip(role, it, () => { remove(i); renderBuild(); })));
  };
  fill("bg-have", "have", build.have, (i) => build.have.splice(i, 1));
  fill("bg-through", "through", build.through, (i) => build.through.splice(i, 1));
  fill("bg-want", "want", build.want, (i) => build.want.splice(i, 1));

  const hint = !build.have.length
    ? "Click your starting data — a rounded type node (e.g. protein.query)."
    : (!build.want.length && !build.through.length)
      ? "Now click what you want: a type node, or a weaver to pick one of its outputs. Click a weaver that fans out to pass THROUGH it (for-each)."
      : "Add more, set a value below, then Run. Click &times; on a chip to remove it.";
  const h = document.getElementById("bg-hint"); if (h) h.innerHTML = hint;
  const v = document.getElementById("bg-value");
  if (v && build.have.length) v.placeholder = "value for " + build.have[0] + ", e.g. TP53";

  // Highlight map read by the draw loop.
  const sel = {};
  build.have.forEach((k) => { sel["type:" + k] = "have"; });
  build.want.forEach((k) => { sel["type:" + k] = "want"; });
  build.through.forEach((cid) =>
    (DATA.network.nodes || []).forEach((n) => { if (n.kind === "op" && n.capability === cid) sel[n.id] = "through"; }));
  buildSel = sel;
  schedulePreview();
}

// Live A→B route preview: plan have→want and dim the network to just that path (off-route
// particles freeze) — like clicking one node. No path → routeFocus stays null, so the gap
// itself shows there's no route. Skipped while a pass-through (traversal) is staged.
// previewSeq invalidates in-flight plans: only the newest request may apply (or clear)
// routeFocus, so a stale response can't re-dim the graph after Reset / a later edit.
let previewTimer = null, previewSeq = 0;
function schedulePreview() { clearTimeout(previewTimer); previewTimer = setTimeout(previewRoute, 130); }

async function previewRoute() {
  const seq = ++previewSeq;
  if (!buildMode || build.through.length || !build.have.length || !build.want.length) { routeFocus = null; return; }
  try {
    const r = await fetch("/api/plan", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({
        from_types: build.have, to_types: build.want,
        policy: document.getElementById("b-policy").value,
      }),
    });
    const d = await r.json();
    if (seq !== previewSeq) return;                         // superseded by a newer selection
    if (!d.ok || !d.path) { routeFocus = null; return; }    // no path → no highlight
    const p = d.path, idmap = {};
    (p.nodes || []).forEach((n) => { if (n.kind === "op") idmap[n.id] = "op:" + n.weaver + ":" + n.capability; });
    const nodes = new Set(), edgeKeys = new Set();
    (p.nodes || []).forEach((n) => nodes.add(n.kind === "op" ? idmap[n.id] : n.id));
    (p.edges || []).forEach((e) => edgeKeys.add((idmap[e.source] || e.source) + ">" + (idmap[e.target] || e.target)));
    routeFocus = { nodes, edgeKeys };
  } catch (e) { if (seq === previewSeq) routeFocus = null; }
}

// Clear all build selection + highlight state synchronously and invalidate any pending plan.
function clearBuild() {
  build.have = []; build.through = []; build.want = [];
  const v = document.getElementById("bg-value"); if (v) v.value = "";
  previewSeq++; clearTimeout(previewTimer);
  routeFocus = null; buildSel = null;
  renderBuild();
}

function closePicker() { if (pickerEl) { pickerEl.remove(); pickerEl = null; } }

// Op node clicked in build mode: offer "pass through (for-each)" if it fans, plus each
// of its outputs as a Want (shared join keys + descriptive leaf outputs).
function openPicker(node, x, y) {
  closePicker();
  const items = [];
  if ((node.set_outputs || []).length)
    items.push(["⤜ pass through (for-each)", true, () => {
      if (!build.through.includes(node.capability)) build.through.push(node.capability);
    }]);
  [...new Set([...(node.output_types || []), ...(node.output_leaves || [])])].forEach((t) =>
    items.push(["want: " + t, false, () => { if (!build.want.includes(t)) build.want.push(t); }]));
  if (!items.length) return;
  const el = document.createElement("div");
  el.className = "picker";
  el.innerHTML = `<div class="pkhead">${esc(node.weaver)} · ${esc(node.capability)}</div>`;
  items.forEach(([label, fan, act]) => {
    const b = document.createElement("button");
    b.className = "pk" + (fan ? " fan" : "");
    b.textContent = label;
    b.onclick = () => { act(); closePicker(); renderBuild(); };
    el.appendChild(b);
  });
  document.body.appendChild(el);
  el.style.left = Math.min(x, innerWidth - el.offsetWidth - 12) + "px";
  el.style.top = Math.min(y, innerHeight - el.offsetHeight - 12) + "px";
  pickerEl = el;
}

function handleBuildClick(node, x, y) {
  closePicker();
  if (!node) return;
  const full = netNodeById(node.id) || node;
  if (full.kind === "type") {
    const k = full.key;
    if (!build.have.length) build.have = [k];
    else if (!build.have.includes(k) && !build.want.includes(k)) build.want.push(k);
    renderBuild();
  } else if (full.kind === "op") {
    openPicker(full, x, y);
  }
}

function enterBuild() {
  buildMode = true; onBuildClick = handleBuildClick;
  if (current !== 0) selectView(0);   // build happens on the network view
  document.getElementById("bg-panel").style.display = "block";
  const b = document.getElementById("b-build");
  b.textContent = "Building — click nodes"; b.classList.add("primary");
  clearBuild();   // always start fresh (also renders the empty panel)
}

function exitBuild() {
  buildMode = false; onBuildClick = null; buildSel = null; routeFocus = null;
  previewSeq++; clearTimeout(previewTimer); closePicker();
  document.getElementById("bg-panel").style.display = "none";
  document.getElementById("b-build").textContent = "Build on the graph";
}

async function runBuild() {
  if (!build.have.length) { document.getElementById("bg-hint").textContent = "Pick a starting type first."; return; }
  if (!build.want.length && !build.through.length) {
    document.getElementById("bg-hint").textContent = "Pick at least one Want, or a pass-through step."; return;
  }
  const value = document.getElementById("bg-value").value.trim();
  if (!value) { document.getElementById("bg-hint").textContent = "Enter a value for " + build.have[0] + "."; return; }
  const btn = document.getElementById("bg-run"); btn.textContent = "running…"; btn.disabled = true;
  const done = () => { btn.textContent = "Run"; btn.disabled = false; };
  try {
    const r = await fetch("/api/run", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({
        have: { [build.have[0]]: value },
        want: build.want,
        traverse: build.through,
        policy: document.getElementById("b-policy").value,
        expand: build.through.length ? "all" : "top", k: 5,
      }),
    });
    const d = await r.json(); done();
    if (!d.ok) { showError(d.error || "no route"); return; }
    lastRun = { columns: d.columns, rows: d.rows, summary: d.summary };
    if (d.path) { addPlanView(d.path); startRunAnim(d.path, d.result); }  // light up the route
    showResults(d);
  } catch (e) { done(); showError(String(e)); }
}

function setupBuilder() {
  if (!SERVED) return;
  document.getElementById("builder").style.display = "block";
  document.getElementById("b-build").onclick = () => (buildMode ? exitBuild() : enterBuild());
  document.getElementById("bg-run").onclick = runBuild;
  document.getElementById("bg-exit").onclick = exitBuild;
  document.getElementById("bg-reset").onclick = clearBuild;
  document.getElementById("bg-value").addEventListener("keydown", (e) => { if (e.key === "Enter") runBuild(); });
  // Dismiss the output picker on any outside click (capture phase: runs before the
  // canvas click that opens a new one, so opening doesn't immediately close it).
  addEventListener("click", (e) => { if (pickerEl && !pickerEl.contains(e.target)) closePicker(); }, true);
  const dl = document.getElementById("b-types");
  (DATA.network.nodes || []).filter((n) => n.kind === "type")
    .map((n) => n.key).sort()
    .forEach((k) => { const o = document.createElement("option"); o.value = k; dl.appendChild(o); });
  document.getElementById("b-plan").onclick = runPlan;
  ["b-have", "b-want"].forEach((id) =>
    document.getElementById(id).addEventListener("keydown", (e) => { if (e.key === "Enter") runPlan(); }));
  document.getElementById("b-search").addEventListener("input", (e) => applySearch(e.target.value));
  document.getElementById("b-save").onclick = saveRecipe;
  document.getElementById("b-recipes").onchange = (e) => { if (e.target.value) loadRecipe(e.target.value); };
  refreshRecipes();
  // Sheet dismissal: the close button, backdrop click, and Escape.
  document.getElementById("sheet-x").onclick = closeSheet;
  document.getElementById("sheet").addEventListener("click", (e) => { if (e.target.id === "sheet") closeSheet(); });
  addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
  // Deep link: #have=...&want=... pre-fills and auto-plans (shareable braid).
  const m = new URLSearchParams(location.hash.slice(1));
  if (m.get("have") || m.get("want")) {
    document.getElementById("b-have").value = (m.get("have") || "").replace(/,/g, ", ");
    document.getElementById("b-want").value = (m.get("want") || "").replace(/,/g, ", ");
    runPlan();
  }
}
"""
