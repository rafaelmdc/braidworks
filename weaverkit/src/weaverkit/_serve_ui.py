"""The interactive (``weaverkit serve``-only) UI, split out of the static template.

``_view_template.py`` is the self-contained *static* network picture. The builder / run /
results / light-up controls are only meaningful when served (they call ``/api/plan`` and
``/api/run``), so they live here and are injected into the page **only when serving**
(``render_html(..., interactive=True)``). A ``file://`` export of ``weaverkit view`` carries
none of this — it stays lean.

Three fragments, slotted into the template's ``__SERVE_CSS__`` / ``__SERVE_HTML__`` /
``__SERVE_JS__`` markers. The JS runs in the template's ``<script>`` scope, so it freely
references the base globals (``DATA``, ``VIEWS``, ``layouts``, ``particles``,
``computeLayout``, ``selectView``, ``esc``) and the base light-up state (``runAnim`` —
written here, read by the draw loop's ``runStatusOf``).
"""

from __future__ import annotations

SERVE_CSS = """
  /* Builder (weaverkit serve only) — top-left, mirrors .panel */
  .builder {
    position: fixed; top: 80px; left: 18px; z-index: 10; width: 300px;
    max-height: calc(100vh - 112px); overflow-y: auto;
    background: var(--panel); backdrop-filter: blur(14px);
    border: 1px solid var(--panel-edge); border-radius: 14px;
    padding: 16px 16px 18px; font-size: 12.5px;
    box-shadow: 0 22px 54px rgba(0,0,0,0.42);
  }
  .builder h2 {
    font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-dim); margin: 0 0 12px;
  }
  .builder label { display: block; margin-bottom: 9px; color: var(--ink-dim); font-size: 11px; }
  .builder input, .builder select {
    width: 100%; margin-top: 4px; box-sizing: border-box;
    background: rgba(10,16,30,0.6); color: var(--ink);
    border: 1px solid var(--panel-edge); border-radius: 8px; padding: 7px 9px; font-size: 12.5px;
  }
  .builder .brow { display: flex; gap: 8px; align-items: stretch; margin-top: 4px; }
  .builder .brow select { width: auto; flex: 1; }
  .builder button.go {
    background: rgba(120,150,220,0.18); color: var(--ink); cursor: pointer;
    border: 1px solid rgba(120,150,220,0.4); border-radius: 8px; padding: 7px 14px; font-size: 12.5px;
  }
  .builder button.go:hover { background: rgba(120,150,220,0.3); }
  .bsearch { margin-bottom: 12px; }
  #b-out { margin-top: 14px; }
  #b-out .berr { color: #e6a3a3; font-size: 11.5px; line-height: 1.45; }
  #b-out .bsum { color: var(--ink); margin-bottom: 10px; }
  .btabs { display: flex; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
  .btab { cursor: pointer; font-size: 10.5px; color: var(--ink-dim);
    border: 1px solid var(--panel-edge); border-radius: 7px; padding: 3px 8px; }
  .btab.on { color: var(--ink); border-color: rgba(120,150,220,0.4); }
  #b-out pre {
    background: rgba(8,12,24,0.7); border: 1px solid var(--panel-edge); border-radius: 8px;
    padding: 9px; font-size: 10.5px; line-height: 1.4; overflow-x: auto; white-space: pre-wrap;
    word-break: break-word; margin: 0;
  }
  .bcopy { cursor: pointer; float: right; font-size: 10px; color: var(--ink-dim);
    border: 1px solid var(--panel-edge); border-radius: 6px; padding: 1px 6px; margin: -2px 0 4px 6px; }
  .bcite { font-size: 10.5px; color: var(--ink-dim); line-height: 1.5; margin-top: 10px; }
  .bcite b { color: var(--ink); }
  .brun { margin-top: 14px; border-top: 1px solid var(--panel-edge); padding-top: 12px; }
  .brun .brow { margin-top: 8px; }
  .brun input[type=number] { width: 56px; }
  /* Results — bottom panel spanning the stage */
  .results {
    position: fixed; left: 18px; right: 18px; bottom: 16px; z-index: 11;
    max-height: 38vh; overflow: auto;
    background: var(--panel); backdrop-filter: blur(14px);
    border: 1px solid var(--panel-edge); border-radius: 14px; padding: 12px 14px;
    box-shadow: 0 22px 54px rgba(0,0,0,0.42); font-size: 12px;
  }
  .results .rhead { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  .results .rhead h2 {
    font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-dim); margin: 0; flex: 1;
  }
  .results table { border-collapse: collapse; width: 100%; }
  .results th, .results td {
    text-align: left; padding: 5px 9px; border-bottom: 1px solid var(--panel-edge);
    white-space: nowrap; max-width: 340px; overflow: hidden; text-overflow: ellipsis;
  }
  .results th { color: var(--ink-dim); font-weight: 600; font-size: 10.5px;
    text-transform: uppercase; letter-spacing: 0.06em; }
  .results td { color: var(--ink); }
  .rclose { cursor: pointer; color: var(--ink-dim); border: 1px solid var(--panel-edge);
    border-radius: 6px; padding: 1px 7px; }
"""

SERVE_HTML = """
<div class="builder" id="builder" style="display:none">
  <h2>Build a braid</h2>
  <input id="b-search" class="bsearch" placeholder="🔍 filter the graph…" autocomplete="off">
  <label>Have (input types)
    <input id="b-have" list="b-types" placeholder="e.g. protein.query" autocomplete="off">
  </label>
  <label>Want (target types)
    <input id="b-want" list="b-types" placeholder="e.g. pdb.id" autocomplete="off">
  </label>
  <datalist id="b-types"></datalist>
  <div class="brow">
    <select id="b-policy" title="backend policy">
      <option value="local_first">local_first</option>
      <option value="api_first">api_first</option>
      <option value="local_only">local_only</option>
      <option value="api_only">api_only</option>
    </select>
    <button class="go" id="b-plan">Plan ▶</button>
  </div>
  <div class="note">Comma-separate multiple types. Autocomplete from the network.</div>
  <div class="brun" id="b-recipes-wrap">
    <label>Recipes
      <select id="b-recipes"><option value="">— load saved —</option></select>
    </label>
    <div class="brow">
      <input id="b-recipe-name" placeholder="name to save" autocomplete="off">
      <button class="go" id="b-save">Save</button>
    </div>
  </div>
  <div id="b-out"></div>
</div>

<div class="results" id="results" style="display:none"></div>
"""

SERVE_JS = r"""
// ---- builder (weaverkit serve only) ----------------------------------------
// Interactive only when served over HTTP; a file:// export stays the static picture.
const SERVED = location.protocol === "http:" || location.protocol === "https:";

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

function copyBtn(text) {
  return `<span class="bcopy" onclick='navigator.clipboard.writeText(this.nextSibling.textContent)'>copy</span>`;
}

function renderArtifacts(d) {
  const a = d.artifacts, p = d.path;
  const tabs = [
    ["weave", "CLI (run)", a.cli_weave],
    ["path", "CLI (route)", a.cli_path],
    ["python", "Python", a.python],
    ["json", "JSON", JSON.stringify(a.braid, null, 2)],
  ];
  let h = `<div class="bsum"><b>${esc(String(p.step_count))}</b> step(s): ` +
    esc(p.from_types.join(", ")) + " → " + esc(p.to_types.join(", ")) + "</div>";
  h += `<div class="btabs">` +
    tabs.map((t, i) => `<span class="btab${i === 0 ? " on" : ""}" data-i="${i}">${esc(t[1])}</span>`).join("") +
    `</div>`;
  h += tabs.map((t, i) =>
    `<div class="bpane" data-i="${i}" style="display:${i === 0 ? "block" : "none"}">` +
    copyBtn() + `<pre>${esc(t[2])}</pre></div>`).join("");
  if (d.citations && d.citations.length) {
    h += `<div class="bcite"><b>Cite</b><br>` + d.citations.map(esc).join("<br>") + `</div>`;
  }
  return h + runControlsHTML(p);
}

function whyNoPath(msg) {
  return `<div class="berr"><b>No route.</b><br>${esc(msg)}</div>`;
}

// ---- run: execute the planned braid, light it up, tabulate ------------------
let lastPlan = null;   // {from, to, policy} of the current built route
let lastRun = null;    // {columns, rows} for export

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

function runControlsHTML(path) {
  const hint = path.from_types.length === 1
    ? `value for <b>${esc(path.from_types[0])}</b>`
    : `<code>type=value</code> pairs, comma-separated`;
  return `<div class="brun">
    <label>Run — ${hint}
      <input id="r-values" placeholder="${esc(path.from_types.join("="))}=…" autocomplete="off"></label>
    <div class="brow">
      <select id="r-expand" title="fan-out policy">
        <option value="top">top 1</option><option value="top_k">top k</option><option value="all">all</option>
      </select>
      <input id="r-k" type="number" min="1" value="3" title="k for top-k">
      <button class="go" id="r-run">Run ▶</button>
    </div></div>`;
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
// on_event fires server-side. (POST /api/run remains for non-streaming callers.)
function runBraid() {
  if (!lastPlan) return;
  const have = parseValues(lastPlan.from, document.getElementById("r-values").value);
  if (!Object.keys(have).length) return;
  const expand = document.getElementById("r-expand").value;
  const k = parseInt(document.getElementById("r-k").value, 10) || 3;
  const btn = document.getElementById("r-run"); btn.textContent = "running…"; btn.disabled = true;
  const done = () => { btn.textContent = "Run ▶"; btn.disabled = false; };
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
      addPlanView(ev.path); startRunAnim(ev.path, ev.result); renderResults(ev);
    } else if (ev.event === "error") { es.close(); done(); renderResults(null, ev.error); }
  };
  es.onerror = () => { es.close(); done(); };
}

function renderResults(d, err) {
  const box = document.getElementById("results");
  box.style.display = "block";
  if (err) { box.innerHTML = `<div class="rhead"><h2>Run failed</h2><span class="rclose" onclick="this.closest('.results').style.display='none'">✕</span></div><div class="berr">${esc(err)}</div>`; return; }
  lastRun = { columns: d.columns, rows: d.rows };
  const s = d.summary;
  const head = `<div class="rhead">
    <h2>Results — ${s.resolved} resolved${s.unresolved ? ", " + s.unresolved + " unresolved" : ""}${s.errors ? ", " + s.errors + " error(s)" : ""}</h2>
    <span class="btab" onclick="exportRows('csv')">CSV</span>
    <span class="btab" onclick="exportRows('tsv')">TSV</span>
    <span class="btab" onclick="exportRows('json')">JSON</span>
    <span class="rclose" onclick="this.closest('.results').style.display='none'">✕</span></div>`;
  if (!d.rows.length) { box.innerHTML = head + `<div class="note">No resolved rows.</div>`; return; }
  const th = d.columns.map((c) => `<th>${esc(c)}</th>`).join("");
  const trs = d.rows.map((row) =>
    "<tr>" + d.columns.map((c) => `<td title="${esc(fmtCell(row[c]))}">${esc(fmtCell(row[c]))}</td>`).join("") + "</tr>").join("");
  box.innerHTML = head + `<table><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table>`;
}

function fmtCell(v) {
  if (v == null) return "";
  if (Array.isArray(v)) return v.join("; ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function exportRows(fmt) {
  if (!lastRun) return;
  const { columns, rows } = lastRun;
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
  if (!from.length || !to.length) { out.innerHTML = whyNoPath("pick a Have and a Want type"); return; }
  out.innerHTML = `<div class="bsum">planning…</div>`;
  try {
    const r = await fetch("/api/plan", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ from_types: from, to_types: to, policy }),
    });
    const d = await r.json();
    if (!d.ok) { out.innerHTML = whyNoPath(d.error || "unroutable"); return; }
    runAnim = null;  // clear any prior run light-up when re-planning
    setHash(from, to);
    addPlanView(d.path);
    lastPlan = { from: d.path.from_types, to: d.path.to_types, policy, path: d.path };
    out.innerHTML = renderArtifacts(d);
    out.querySelectorAll(".btab[data-i]").forEach((tab) => {
      tab.onclick = () => {
        const i = tab.dataset.i;
        out.querySelectorAll(".btab[data-i]").forEach((t) => t.classList.toggle("on", t === tab));
        out.querySelectorAll(".bpane").forEach((p) => { p.style.display = p.dataset.i === i ? "block" : "none"; });
      };
    });
    const runBtn = document.getElementById("r-run");
    if (runBtn) {
      runBtn.onclick = runBraid;
      const rv = document.getElementById("r-values");
      rv.addEventListener("keydown", (e) => { if (e.key === "Enter") runBraid(); });
    }
  } catch (e) { out.innerHTML = whyNoPath(String(e)); }
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
  sel.innerHTML = '<option value="">— load saved —</option>' +
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

function setupBuilder() {
  if (!SERVED) return;
  document.getElementById("builder").style.display = "block";
  const dl = document.getElementById("b-types");
  (DATA.network.nodes || []).filter((n) => n.kind === "type")
    .map((n) => n.key).sort()
    .forEach((k) => { const o = document.createElement("option"); o.value = k; dl.appendChild(o); });
  document.getElementById("b-plan").onclick = runPlan;
  ["b-have", "b-want"].forEach((id) =>
    document.getElementById(id).addEventListener("keydown", (e) => { if (e.key === "Enter") runPlan(); }));
  // Graph search filter.
  document.getElementById("b-search").addEventListener("input", (e) => applySearch(e.target.value));
  // Recipes: save current build / load a saved one.
  document.getElementById("b-save").onclick = saveRecipe;
  document.getElementById("b-recipes").onchange = (e) => { if (e.target.value) loadRecipe(e.target.value); };
  refreshRecipes();
  // Deep link: #have=...&want=... pre-fills and auto-plans (shareable braid).
  const m = new URLSearchParams(location.hash.slice(1));
  if (m.get("have") || m.get("want")) {
    document.getElementById("b-have").value = (m.get("have") || "").replace(/,/g, ", ");
    document.getElementById("b-want").value = (m.get("want") || "").replace(/,/g, ", ");
    runPlan();
  }
}
"""
