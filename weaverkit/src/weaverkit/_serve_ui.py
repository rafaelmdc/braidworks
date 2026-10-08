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
  .rerrs { margin: 0 0 14px; display: flex; flex-direction: column; gap: 8px; }
  .rerr { background: rgba(224,112,110,0.10); border: 1px solid rgba(224,112,110,0.4);
    border-radius: 9px; padding: 9px 11px; font-size: 11.5px; line-height: 1.45; color: #f0c2c0; }
  .rerr b { color: #e6a3a3; }
  .rerr .dim { color: var(--ink-dim); font-weight: 400; }
  .rerr > div { color: var(--ink); margin-top: 3px; word-break: break-word; }
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

  /* --- Floating per-weaver param cards (anchored to the node on the graph) --- */
  #paramcards { position: fixed; inset: 0; z-index: 13; pointer-events: none; }
  .paramcard { position: absolute; pointer-events: auto; width: 208px;
    background: var(--panel); backdrop-filter: blur(14px); border: 1px solid rgba(232,192,105,0.5);
    border-radius: 11px; padding: 9px 11px; font-size: 12px;
    box-shadow: 0 16px 42px rgba(0,0,0,0.5); }
  .paramcard .pc-h { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em;
    color: #f0d18a; margin-bottom: 7px; }
  .paramcard .rf-row { margin-bottom: 8px; }
  .paramcard .rf-row:last-child { margin-bottom: 0; }
  .paramcard label.rf-l { display: block; font-size: 11px; color: var(--ink); margin-bottom: 3px; }
  .paramcard input, .paramcard select { width: 100%; box-sizing: border-box;
    background: rgba(10,16,30,0.6); color: var(--ink); border: 1px solid var(--panel-edge);
    border-radius: 7px; padding: 6px 8px; font-size: 12px; }
  .paramcard input:focus, .paramcard select:focus { outline: none; border-color: rgba(232,192,105,0.6); }
  .paramcard .rf-desc { font-size: 9.5px; color: var(--ink-dim); margin-top: 3px; line-height: 1.32; }
"""

SERVE_HTML = """
<div class="builder" id="builder" style="display:none">
  <h2>Build</h2>
  <div class="bgroup"><label class="blabel" for="b-search">Find an input or output</label>
    <input id="b-search" placeholder="e.g. biological processes" autocomplete="off">
    <div id="b-search-results" aria-live="polite"></div></div>

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
    <label for="bg-value" class="blabel">Input values (shared values for batches)</label>
    <input id="bg-value" placeholder="value, e.g. TP53" autocomplete="off">
    <div class="note">For a batch, leave this empty or use it for values shared by every row.</div>
    <label for="bg-expand" class="blabel">Expansion</label>
    <select id="bg-expand"><option value="auto">automatic (top 1; all for pass-through)</option>
      <option value="top">top 1</option><option value="top_k">top k</option><option value="all">all</option></select>
    <label for="bg-k" class="blabel">k</label><input id="bg-k" type="number" min="1" value="5">
    <label for="bg-limit" class="blabel">Maximum leaves</label><input id="bg-limit" type="number" min="1" value="10000">
    <div class="brow" style="margin-top:8px">
      <button class="btn primary" id="bg-run">Run</button>
      <button class="btn ghost" id="bg-code">Code</button>
      <button class="btn ghost" id="bg-reset">Reset</button>
      <button class="btn ghost" id="bg-exit">Exit</button>
    </div>
  </div>

  <label for="b-review-policy" class="blabel">Ambiguous matches</label>
  <select id="b-review-policy">
    <option value="halt">pause for review (default)</option>
    <option value="allow_continue">select or expand candidates automatically</option>
    <option value="raise">fail immediately</option>
  </select>
  <label for="b-confidence" class="blabel">Minimum confidence (0–1)</label>
  <input id="b-confidence" type="number" min="0" max="1" step="0.01" value="0">
  <div class="note">Automatic selection keeps the review flag. Results below the confidence floor still pause.</div>

  <details id="b-batch-panel" style="margin-top:12px">
    <summary class="blabel">Batch inputs</summary>
    <label><input id="b-batch-enabled" type="checkbox"> Run multiple starting rows</label>
    <label class="blabel" for="b-batch-format">Input format</label>
    <select id="b-batch-format"><option value="lines">One value per line</option>
      <option value="csv">CSV with type-id headers</option><option value="tsv">TSV with type-id headers</option></select>
    <label class="blabel" for="b-batch-type">Type for one-value-per-line input</label>
    <input id="b-batch-type" list="b-types" placeholder="protein.query">
    <label class="blabel" for="b-batch-file">Upload text, CSV or TSV</label>
    <input id="b-batch-file" type="file" accept=".txt,.csv,.tsv,text/plain,text/csv">
    <label class="blabel" for="b-batch-text">Or paste inputs</label>
    <textarea id="b-batch-text" rows="6" style="width:100%;box-sizing:border-box" placeholder="TP53&#10;BRCA1"></textarea>
    <div class="note">Table headers are type IDs. Empty cells are absent inputs. Duplicates keep separate source rows. Row values override shared values.</div>
  </details>
  <details id="b-persistence" style="margin-top:12px">
    <summary class="blabel">Cache and saved runs (optional)</summary>
    <p class="note">Files are stored on the machine running Braidworks. Leave paths empty for memory-only execution.</p>
    <label class="blabel" for="b-cache-db">Lookup cache file</label><input id="b-cache-db" placeholder="data/lookups.sqlite">
    <label class="blabel" for="b-run-db">Saved runs file</label><input id="b-run-db" placeholder="data/runs.sqlite">
    <label class="blabel" for="b-run-id">New run name (optional)</label><input id="b-run-id" placeholder="automatic unique name">
    <button class="btn" id="b-runs" style="margin-top:8px">Saved runs</button>
    <div id="b-saved-run" class="note" role="status"></div>
    <details><summary class="blabel">Retention and ownership settings</summary>
      <label class="blabel" for="b-cache-positive">Positive cache lifetime (seconds)</label><input id="b-cache-positive" type="number" min="0" value="3600">
      <label class="blabel" for="b-cache-negative">No-match lifetime (seconds)</label><input id="b-cache-negative" type="number" min="0" value="300">
      <label class="blabel" for="b-cache-bytes">Cache payload budget (bytes)</label><input id="b-cache-bytes" type="number" min="0" value="268435456">
      <label class="blabel" for="b-lease">Run ownership timeout (seconds)</label><input id="b-lease" type="number" min="0.001" step="any" value="60">
    </details>
  </details>
  <div id="b-progress" role="status" aria-live="polite"></div>
  <button id="b-cancel" class="btn" hidden>Cancel run</button>
  <details style="margin-top:12px">
    <summary class="blabel" style="cursor:pointer">Type it instead (advanced)</summary>
    <div class="bgroup" style="margin-top:8px">
      <label class="blabel" for="b-have">Have</label>
      <input id="b-have" list="b-types" placeholder="protein.query" autocomplete="off">
    </div>
    <div class="bgroup">
      <label class="blabel" for="b-want">Want</label>
      <input id="b-want" list="b-types" placeholder="pdb.id" autocomplete="off">
    </div>
    <datalist id="b-types"></datalist>
    <div class="brow">
      <button class="btn primary" id="b-plan">Plan</button>
    </div>
    <div class="note" style="margin-top:8px">Comma-separate multiple types. Autocomplete from the network.</div>
  </details>

  <div class="bgroup" style="margin-top:11px">
    <label class="blabel" for="b-policy">Backend</label>
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

<!-- Floating per-weaver param cards, anchored to the route's param-bearing nodes. -->
<div id="paramcards"></div>

<div class="sheet-backdrop" id="sheet" hidden>
  <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" tabindex="-1">
    <div class="sheet-head"><h3 id="sheet-title"></h3><button class="sheet-x" id="sheet-x" aria-label="Close dialog">&times;</button></div>
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
let sheetReturnFocus = null;
function openSheet(title, html) {
  if (document.getElementById("sheet").hidden) sheetReturnFocus = document.activeElement;
  document.getElementById("sheet-title").textContent = title;
  document.getElementById("sheet-body").innerHTML = html;
  document.getElementById("sheet").hidden = false;
  document.getElementById("sheet-x").focus();
}
function closeSheet() {
  document.getElementById("sheet").hidden = true;
  if (sheetReturnFocus && sheetReturnFocus.isConnected) sheetReturnFocus.focus();
}

// A copyable code/text block (copy button copies the following <pre>'s text).
function copyBlock(text) {
  return `<div class="copyrow"><button class="btn ghost copy">copy</button></div><pre>${esc(text)}</pre>`;
}
function wireCopies() {
  document.querySelectorAll("#sheet-body .copy").forEach((b) => {
    b.onclick = () => navigator.clipboard.writeText(b.parentElement.nextElementSibling.textContent);
  });
}

async function showCode() {
  let a, body;
  try {
    body = toQueryRequest(experimentState(), {placeholders: true});
    const response = await fetch("/api/code", {method: "POST", headers: {"content-type": "application/json"},
      body: JSON.stringify(body)});
    const doc = await response.json();
    if (!doc.ok) { showError(doc.error || "Could not generate code."); return; }
    a = doc.artifacts;
  } catch (e) { showError(String(e)); return; }
  const tabs = [
    ["weave", "Run (CLI)", a.cli_weave],
    ["path", "Route (CLI)", a.cli_path],
    ["python", "Python", a.python],
    ["json", "Braid JSON", JSON.stringify(a.braid, null, 2)],
  ];
  const head = `<div class="tabs">` +
    tabs.map((t, i) => `<button class="tab${i === 0 ? " on" : ""}" data-i="${i}">${esc(t[1])}</button>`).join("") +
    `</div>`;
  const panes = tabs.map((t, i) =>
    `<div class="pane" data-i="${i}" style="display:${i === 0 ? "block" : "none"}">${copyBlock(t[2])}</div>`
  ).join("");
  const placeholder = Object.values(body.have).includes("<value>") ?
    `<div class="note">Enter your input value, or replace the quoted &lt;value&gt; placeholders before running.</div>` : "";
  openSheet("Generated code", placeholder + head + panes);
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
    <label for="r-limit" class="blabel">Maximum leaves</label>
    <input id="r-limit" type="number" min="1" value="10000">
    <div id="r-params"></div>
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
let activeRun = null;
function batchState(from) {
  if (!document.getElementById("b-batch-enabled").checked) return null;
  return {text: document.getElementById("b-batch-text").value,
          format: document.getElementById("b-batch-format").value,
          input_type: document.getElementById("b-batch-type").value.trim() || from[0] || ""};
}

async function streamRun(body, btn, path, endpoint = "/api/run/stream") {
  if (activeRun) return;
  const controller = new AbortController(); activeRun = controller;
  clearRunState();
  const originalLabel = btn.textContent;
  btn.textContent = "running…"; btn.disabled = true;
  const cancel = document.getElementById("b-cancel"), progress = document.getElementById("b-progress");
  cancel.hidden = false; cancel.onclick = () => controller.abort();
  progress.textContent = "Validating and running inputs…";
  if (path) initLiveAnim(path);
  let finished = false, runIdentity = body.run_id || (body.persistence || {}).run_id;
  try {
    const response = await fetch(endpoint, {method: "POST", signal: controller.signal,
      headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
    if (!response.ok) throw new Error("Server rejected the request: " + response.status);
    const reader = response.body.getReader(), decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value || new Uint8Array(), {stream: !chunk.done});
      buffer = buffer.replace(/\r\n/g, "\n");
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
        if (!data) continue;
        const event = JSON.parse(data);
        if (event.event === "checkpoint") {
          runIdentity = event.run_id;
          document.getElementById("b-saved-run").textContent = "Saved run: " + event.run_id + " (" + event.status + ")";
        } else if (event.event === "progress") {
          progress.textContent = event.completed_inputs + " / " + event.input_count + " input rows completed.";
        } else if (event.event === "wave") {
          if (runAnim) runAnim.revealedWave = event.wave;
          progress.textContent = "Completed execution wave " + (event.wave + 1) + ".";
        } else if (event.event === "error") throw new Error(event.error);
        else if (event.event === "done") {
          finished = true;
          if (event.path) { addPlanView(event.path); startRunAnim(event.path, event.result); }
          progress.textContent = "Finished " + event.summary.inputs + " input row(s).";
          showResults(event);
          const rb = document.getElementById("b-results");
          if (rb) { rb.style.display = ""; rb.onclick = () => showResults(); }
        }
      }
      if (chunk.done) break;
    }
    if (!finished) throw new Error("The connection ended before results arrived. Retry the run.");
  } catch (error) {
    runAnim = null;
    if (controller.signal.aborted) progress.textContent = runIdentity ? "Run cancelled. Continue saved run " + runIdentity + " from Saved runs." : "Run cancelled. No completed batch results were returned.";
    else { progress.textContent = "Run failed."; showError(String(error)); }
  } finally {
    controller.abort();
    btn.textContent = originalLabel; btn.disabled = false;
    if (activeRun === controller) { activeRun = null; cancel.hidden = true; }
  }
}

function runBraid() {
  if (!lastPlan) return;
  try {
    const body = toQueryRequest(experimentState());
    if (!body.batch && !Object.keys(body.have).length) { showError("Enter input values."); return; }
    return streamRun(body, document.getElementById("r-run"), lastPlan.path);
  } catch (e) { showError(String(e)); }
}

function fmtCell(v) {
  if (v == null) return "";
  if (Array.isArray(v)) return v.some((x) => typeof x === "object") ? JSON.stringify(v) : v.join("; ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function showError(msg) {
  openSheet("Run failed", `<div class="berr">${esc(msg)}</div>`);
}

function clearRunState() {
  lastRun = null;
  runAnim = null;
  const results = document.getElementById("b-results");
  if (results) results.style.display = "none";
}

// Which columns to show: by default just the requested wants (the rest — intermediate
// join keys + the whole output group the weaver computed — are hidden behind the toggle).
let resultsShowAll = false;
function visibleCols() {
  if (!lastRun) return [];
  const { columns, want } = lastRun;
  if (resultsShowAll || !(want && want.length)) return columns;
  // Always show EVERY requested want as a column (blank where a row didn't produce it),
  // so a want that resolved for no/some rows still appears — never collapses to one.
  const essential = lastRun.identity_columns || ["entity", "parent", "status", "source_row", "outcome", "missing", "requires_review"];
  return [...new Set([...essential.filter((c) => columns.includes(c)), ...want])];
}
function toggleShowAll() { resultsShowAll = !resultsShowAll; showResults(); }

// Results as a modal page (never overlaps the graph; bounded + scrolls).
function showResults(d) {
  if (d) lastRun = { columns: d.columns, rows: d.rows, summary: d.summary, want: d.want || [], errors: d.errors || [],
                     result: d.result, identity_columns: d.identity_columns, effective_params: d.effective_params || {},
                     review_policy: d.review_policy || "halt", confidence_threshold: d.confidence_threshold || 0, run: d.run || null };
  if (!lastRun) return;
  const { rows, summary, want } = lastRun;
  const columns = visibleCols();
  const hidden = (lastRun.columns || []).filter((c) => !columns.includes(c)).length;
  const s = summary || { resolved: rows.length, unresolved: 0, errors: 0 };
  let body = `<div class="rcounts">${s.resolved} resolved` +
    (s.unresolved ? `, ${s.unresolved} unresolved` : "") +
    (s.review ? `, ${s.review} need review` : "") +
    (s.errors ? `, ${s.errors} diagnostic(s)` : "") +
    (s.truncated_forks ? `, ${s.truncated_forks} truncated fork(s)` : "") + `</div>`;
  body += "<div class=note>Ambiguous matches: " + esc(lastRun.review_policy) + " · minimum confidence: " + esc(String(lastRun.confidence_threshold)) + "</div>";
  const settings = Object.entries(lastRun.effective_params || {}).flatMap(([cap, ps]) =>
    Object.entries(ps).map(([name, value]) => `${cap}.${name}: ${value == null ? "unset" : value}`));
  if (settings.length) body += `<div class="note">Effective parameters: ${esc(settings.join(" · "))}</div>`;
  // Surface the actual error messages so a 0-results run is diagnosable.
  const errs = lastRun.errors || [];
  if (errs.length) {
    body += `<div class="rerrs">` + errs.map((e) => {
      const where = [e.capability, e.entity].filter(Boolean).join(" · ");
      const tag = e.type ? `<b>${esc(e.type)}</b>` : "";
      return `<div class="rerr">${tag}${where ? ` <span class="dim">(${esc(where)})</span>` : ""}` +
        `<div>${esc(e.message || "(no message)")}</div></div>`;
    }).join("") + `</div>`;
  }
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
    body += `<div class="note">No terminal rows.</div>`;
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
  if (fmt === "json") { text = JSON.stringify({ rows, result: lastRun.result,
      effective_params: lastRun.effective_params, review_policy: lastRun.review_policy,
      confidence_threshold: lastRun.confidence_threshold }, null, 2); mime = "application/json"; }
  else {
    const sep = fmt === "tsv" ? "\t" : ",";
    const q = (v) => { const s = typeof v === "object" && v != null ? JSON.stringify(v) : fmtCell(v);
      return s.includes(sep) || /["\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    text = [columns.join(sep), ...rows.map((r) => columns.map((c) => q(r[c])).join(sep))].join("\n");
    mime = fmt === "tsv" ? "text/tab-separated-values" : "text/csv";
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: mime }));
  a.download = "braidworks-results." + fmt;
  a.click(); URL.revokeObjectURL(a.href);
}

async function runPlan() {
  if (buildMode) exitBuild();
  const out = document.getElementById("b-out");
  const from = splitTypes(document.getElementById("b-have").value);
  const to = splitTypes(document.getElementById("b-want").value);
  const policy = document.getElementById("b-policy").value;
  if (!from.length || !to.length) { out.innerHTML = `<div class="berr">Pick a Have and a Want type.</div>`; return; }
  out.innerHTML = `<div class="note">planning…</div>`;
  try {
    const r = await fetch("/api/plan", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(toPlanRequest({from, want: to, policy})),
    });
    const d = await r.json();
    if (!d.ok) { out.innerHTML = `<div class="berr"><b>No route.</b><br>${esc(d.error || "unroutable")}</div>`; return; }
    runAnim = null; lastRun = null;        // clear any prior run state when re-planning
    lastDoc = d;
    lastPlan = { from: d.path.from_types, to: d.path.to_types, policy, path: d.path };
    setHash(from, to);
    addPlanView(d.path);
    out.innerHTML = buildResultHTML(d.path);
    lastParameterCaps = d.parameter_capabilities || [];
    lastRoutePath = d.path;
    const controls = document.getElementById("r-params");
    controls.innerHTML = lastParameterCaps.map((c) => `<div class="pc-h">${esc(c.weaver)} · ${esc(c.capability)}</div>` +
      c.parameters.map((p) => paramControlHTML(c.capability, p, "typed")).join("")).join("");
    bindParamControls(controls);
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
  const results = document.getElementById("b-search-results");
  results.innerHTML = "";
  if (!q) { searchHits = null; return; }
  const hits = new Set();
  const matching = [];
  (layouts[current].nodes || new Map()).forEach((node) => {
    const n = netNodeById(node.id) || node;
    const outputs = [...new Set([...(n.output_types || []), ...(n.output_leaves || [])])];
    const hay = [n.label, n.key, n.weaver, n.capability, n.description,
                 ...outputs, ...Object.values(n.output_descriptions || {})].filter(Boolean).join(" ").toLowerCase();
    if (hay.includes(q)) {
      hits.add(n.id);
      if (n.kind === "type") {
        matching.push({key: n.key, role: "have", label: "Have: " + n.key});
        matching.push({key: n.key, role: "want", label: "Want: " + n.key});
      }
      if (n.kind === "op" && (n.set_outputs || []).length)
        matching.push({key: n.capability, role: "through", label: "Pass through: " + n.capability});
      outputs.filter((key) => (key + " " + ((n.output_descriptions || {})[key] || "")).toLowerCase().includes(q))
        .forEach((key) => matching.push({key, role: "want", label: "Want: " + key}));
    }
  });
  searchHits = hits;
  matching.slice(0, 30).forEach((match) => {
    const button = document.createElement("button"); button.className = "btn ghost";
    button.textContent = match.label;
    button.onclick = () => {
      if (!buildMode) enterBuild();
      if (match.role === "have") build.have = [match.key];
      else if (match.role === "through") { if (!build.through.includes(match.key)) build.through.push(match.key); }
      else if (!build.want.includes(match.key)) build.want.push(match.key);
      renderBuild();
    };
    results.appendChild(button);
  });
  if (!matching.length) results.textContent = hits.size ? "Matching capabilities are highlighted on the graph." : "No matching input or output.";
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

function normalizePersistence(value = {}) {
  const policy = value.cache_policy || {};
  const configuration = {version: 1, cache_db: value.cache_db || null, run_db: value.run_db || null,
    run_id: value.run_id || null, lease_seconds: Number(value.lease_seconds ?? 60),
    cache_policy: {positive_ttl: Number(policy.positive_ttl ?? 3600), negative_ttl: Number(policy.negative_ttl ?? 300),
                   max_payload_bytes: Number(policy.max_payload_bytes ?? 268435456)}};
  if ((configuration.run_id && !configuration.run_db) || !Number.isFinite(configuration.lease_seconds) || configuration.lease_seconds <= 0 ||
      !Number.isFinite(configuration.cache_policy.positive_ttl) || configuration.cache_policy.positive_ttl < 0 ||
      !Number.isFinite(configuration.cache_policy.negative_ttl) || configuration.cache_policy.negative_ttl < 0 ||
      !Number.isInteger(configuration.cache_policy.max_payload_bytes) || configuration.cache_policy.max_payload_bytes < 0)
    throw new Error("Check cache lifetimes, payload budget, saved runs path and ownership timeout.");
  return configuration;
}

function persistenceState() {
  return normalizePersistence({cache_db: document.getElementById("b-cache-db").value.trim(),
    run_db: document.getElementById("b-run-db").value.trim(), run_id: document.getElementById("b-run-id").value.trim(),
    cache_policy: {positive_ttl: document.getElementById("b-cache-positive").value,
                   negative_ttl: document.getElementById("b-cache-negative").value,
                   max_payload_bytes: document.getElementById("b-cache-bytes").value},
    lease_seconds: document.getElementById("b-lease").value});
}

function restorePersistence(value) {
  const options = normalizePersistence(value || {});
  document.getElementById("b-cache-db").value = options.cache_db || "";
  document.getElementById("b-run-db").value = options.run_db || "";
  document.getElementById("b-run-id").value = options.run_id || "";
  document.getElementById("b-cache-positive").value = options.cache_policy.positive_ttl;
  document.getElementById("b-cache-negative").value = options.cache_policy.negative_ttl;
  document.getElementById("b-cache-bytes").value = options.cache_policy.max_payload_bytes;
  document.getElementById("b-lease").value = options.lease_seconds;
}

async function showSavedRuns() {
  try {
    const path = document.getElementById("b-run-db").value.trim();
    if (!path) throw new Error("Enter the saved runs file path first.");
    const response = await fetch("/api/runs?run_db=" + encodeURIComponent(path));
    const data = await response.json();
    if (!data.ok) throw new Error(data.error);
    openSheet("Saved runs", data.runs.length ? data.runs.map((run) =>
      `<div class="summary"><b>${esc(run.run_id)}</b> · ${esc(run.status)} · ${run.inputs} inputs
       <div class="bactions"><button class="btn inspect-run" data-run-id="${esc(run.run_id)}">Inspect</button></div></div>`).join("") : "<p>No saved runs in this file.</p>");
    document.querySelectorAll(".inspect-run").forEach((button) => button.onclick = () => inspectSavedRun(button.dataset.runId));
  } catch (error) { showError(String(error)); }
}

async function inspectSavedRun(runId) {
  try {
    const options = persistenceState(); options.run_id = null;
    const response = await fetch("/api/run/status?" + new URLSearchParams({run_db: options.run_db, run_id: runId}));
    const data = await response.json();
    if (!data.ok) throw new Error(data.error);
    const run = data.run;
    const reviews = run.reviews.map((item, i) => {
      const row = item.strand_set, observation = item.triggering_result;
      const candidates = observation.candidates.map((candidate, index) => {
        const values = Object.fromEntries(candidate.strands.map((strand) => [strand.type_id, strand.value]));
        return `<option value="select:${index}">Candidate ${index+1} (confidence ${candidate.confidence}): ${esc(JSON.stringify(values))}</option>`;
      }).join("");
      return `<label class="blabel" for="review-${i}">Row ${row.source_row ?? ""}: ${esc(row.entity_id)} · ${esc(observation.capability_id)} (${esc(row.execution_key)})</label>
        <select id="review-${i}" class="review-choice" data-key="${esc(row.execution_key)}"><option value="">Leave pending</option>${candidates}
        ${observation.status === "ok" ? '<option value="accept">Accept this observation</option>' : ''}<option value="reject">Reject this row</option></select>`;
    }).join("");
    openSheet("Run " + runId, `<p class="note">${esc(run.status)} · revision ${run.revision} · ${run.inputs} inputs. Saved query settings apply when continuing.</p>
      <details><summary>Saved query settings</summary><pre>${esc(JSON.stringify({request:run.request,planned_routes:run.planned_routes},null,2))}</pre></details>
      ${reviews}<div class="bactions"><button id="resume-saved" class="btn primary">${run.status === 'complete' ? 'View results' : 'Continue saved run'}</button></div>`);
    document.getElementById("resume-saved").onclick = () => {
      const decisions = [...document.querySelectorAll(".review-choice")].filter((el) => el.value).map((el) => {
        const [action, index] = el.value.split(":");
        return {version:1,entity_key:el.dataset.key,action,candidate_index:action === "select" ? Number(index) : null};
      });
      if (run.status === "review" && !decisions.length) { showError("Choose an explicit review decision first."); return; }
      const button = document.getElementById("resume-saved");
      return streamRun({run_id:runId,persistence:options,decisions}, button, null, "/api/resume/stream");
    };
  } catch (error) { showError(String(error)); }
}

// Pure experiment values: DOM reading, execution data and animation stay separate.
function normalizeExperiment(value) {
  const clone = (x) => JSON.parse(JSON.stringify(x));
  const types = (x) => [...new Set((x || []).map((t) => String(t).trim()).filter(Boolean))];
  const state = {version: 2, mode: value.mode === "graph" ? "graph" : "typed",
    from: types(value.from), want: types(value.want), traverse: (value.traverse || []).slice(),
    values: clone(value.values || {}), batch: value.batch ? clone(value.batch) : null,
    params: clone(value.params || {}), persistence: normalizePersistence(value.persistence || {}), policy: value.policy || "local_first",
    review_policy: value.review_policy || "halt",
    confidence_threshold: Number(value.confidence_threshold ?? 0),
    expand: value.expand || "top", k: Number(value.k ?? 3),
    max_expansion: Number(value.max_expansion ?? 10000)};
  if (!["auto", "top", "top_k", "all"].includes(state.expand) ||
      !Number.isInteger(state.k) || state.k < 1 ||
      !Number.isInteger(state.max_expansion) || state.max_expansion < 1 ||
      !Number.isFinite(state.confidence_threshold) || state.confidence_threshold < 0 || state.confidence_threshold > 1)
    throw new Error("Check expansion, maximum leaves and confidence settings.");
  return state;
}

function toQueryRequest(value, {placeholders = false} = {}) {
  const state = normalizeExperiment(value);
  const have = state.batch ? state.values : Object.fromEntries(state.from
    .filter((key) => Object.hasOwn(state.values, key) || placeholders)
    .map((key) => [key, state.values[key] ?? "<value>"]));
  return {have, batch: state.batch, want: state.want, traverse: state.traverse,
    policy: state.policy, review_policy: state.review_policy, confidence_threshold: state.confidence_threshold,
    params: state.params, expand: state.expand === "auto" ? (state.traverse.length ? "all" : "top") : state.expand,
    k: state.k, max_expansion: state.max_expansion, persistence: state.persistence};
}

function toPlanRequest(value) {
  const state = normalizeExperiment(value), query = toQueryRequest(state);
  return {from_types: state.from, to_types: query.want, traverse: query.traverse,
    policy: query.policy};
}

function experimentState() {
  const mode = buildMode ? "graph" : "typed";
  const from = buildMode ? build.have.slice() : lastPlan ? lastPlan.from.slice() : splitTypes(document.getElementById("b-have").value);
  const want = buildMode ? build.want.slice() : lastPlan ? lastPlan.to.slice() : splitTypes(document.getElementById("b-want").value);
  const valueInput = document.getElementById(buildMode ? "bg-value" : "r-values");
  const values = valueInput ? parseValues(from, valueInput.value) : {};
  const expandInput = document.getElementById(buildMode ? "bg-expand" : "r-expand");
  const expand = expandInput ? expandInput.value : "top";
  const kInput = document.getElementById(buildMode ? "bg-k" : "r-k");
  const limitInput = document.getElementById(buildMode ? "bg-limit" : "r-limit");
  return normalizeExperiment({ version: 2, mode, from, want, values, persistence: persistenceState(), batch: batchState(from), traverse: buildMode ? build.through.slice() : [],
    policy: document.getElementById("b-policy").value,
    review_policy: document.getElementById("b-review-policy").value,
    confidence_threshold: Number(document.getElementById("b-confidence").value || 0),
    params: collectParams(), expand, k: Number(kInput && kInput.value || 3),
    max_expansion: Number(limitInput && limitInput.value || 10000) });
}

function recipeFeedback(message) {
  let el = document.getElementById("recipe-feedback");
  if (!el) { el = document.createElement("div"); el.id = "recipe-feedback";
    el.className = "note"; el.setAttribute("role", "status");
    document.getElementById("b-recipes").after(el); }
  el.textContent = message;
}

function saveRecipe() {
  const name = (document.getElementById("b-recipe-name").value || "").trim();
  let state;
  try { state = experimentState(); } catch (e) { recipeFeedback(String(e)); return; }
  if (!name || !state.from.length || (!state.want.length && !state.traverse.length)) {
    recipeFeedback("Enter a name and choose Have plus Want or a pass-through step."); return;
  }
  try {
    const recipes = { ...loadRecipes(), [name]: state };
    localStorage.setItem(RECIPES_KEY, JSON.stringify(recipes));
    document.getElementById("b-recipe-name").value = "";
    refreshRecipes();
    document.getElementById("b-recipes").value = name;
    recipeFeedback("Saved " + name + ".");
  } catch (e) { recipeFeedback("Could not save: " + String(e)); }
}

async function loadRecipe(name) {
  let r = loadRecipes()[name];
  if (!r) return;
  if (!r.version) { // legacy typed recipe: have/want are type-name strings
    if (buildMode) exitBuild();
    document.getElementById("b-have").value = r.have || "";
    document.getElementById("b-want").value = r.want || "";
    if (r.policy) document.getElementById("b-policy").value = r.policy;
    document.getElementById("b-review-policy").value = "halt";
    document.getElementById("b-confidence").value = 0;
    document.getElementById("b-batch-enabled").checked = false;
    restorePersistence(null);
    paramVals = {}; await runPlan(); recipeFeedback("Loaded " + name + "."); return;
  }
  if (r.version !== 2 || !Array.isArray(r.from) || !Array.isArray(r.want) || !Array.isArray(r.traverse)) {
    recipeFeedback("This recipe format is unsupported."); return;
  }
  try { r = normalizeExperiment(r); }
  catch (e) { recipeFeedback(String(e)); return; }
  restorePersistence(r.persistence);
  document.getElementById("b-policy").value = r.policy || "local_first";
  document.getElementById("b-review-policy").value = r.review_policy || "halt";
  document.getElementById("b-confidence").value = r.confidence_threshold || 0;
  if (r.mode === "graph") {
    if (!buildMode) enterBuild(); else clearBuild();
    build.have = r.from.slice(); build.want = r.want.slice(); build.through = r.traverse.slice();
    paramVals = JSON.parse(JSON.stringify(r.params || {}));
    document.getElementById("bg-value").value = r.from.length === 1 ? (r.values || {})[r.from[0]] || "" :
      r.from.filter((key) => key in (r.values || {})).map((key) => key + "=" + r.values[key]).join(", ");
    document.getElementById("bg-expand").value = r.expand || "auto";
    document.getElementById("bg-k").value = r.k || 3;
    document.getElementById("bg-limit").value = r.max_expansion || 10000;
    renderBuild(); await previewRoute();
  } else {
    if (buildMode) exitBuild();
    document.getElementById("b-have").value = r.from.join(", ");
    document.getElementById("b-want").value = r.want.join(", ");
    paramVals = JSON.parse(JSON.stringify(r.params || {}));
    await runPlan();
    const values = r.values || {};
    const valueInput = document.getElementById("r-values");
    if (valueInput) valueInput.value = r.from.length === 1 ? (values[r.from[0]] || "") :
      r.from.filter((key) => key in values).map((key) => key + "=" + values[key]).join(", ");
    const expandInput = document.getElementById("r-expand");
    if (expandInput) expandInput.value = r.expand || "top";
    const kInput = document.getElementById("r-k"); if (kInput) kInput.value = r.k || 3;
    const limitInput = document.getElementById("r-limit"); if (limitInput) limitInput.value = r.max_expansion || 10000;
  }
  document.getElementById("b-batch-enabled").checked = !!r.batch;
  document.getElementById("b-batch-text").value = r.batch ? r.batch.text || "" : "";
  document.getElementById("b-batch-format").value = r.batch ? r.batch.format || "lines" : "lines";
  document.getElementById("b-batch-type").value = r.batch ? r.batch.input_type || "" : "";
  recipeFeedback("Loaded " + name + ".");
}

// ---- click-to-build: pick have / pass-through / want on the graph ----------
// build.have/want hold type keys; build.through holds fan capability ids (--for-each).
const build = { have: [], through: [], want: [] };
let pickerEl = null;
let lastParameterCaps = [];
let lastRoutePath = null;   // last previewed plan (its op nodes name the route's capabilities)
let paramVals = {};         // {capability_id: {name: value}} — persists across re-renders

function netNodeById(id) { return (DATA.network.nodes || []).find((n) => n.id === id); }

function buildChip(role, label, onRemove) {
  const c = document.createElement("span");
  c.className = "chip-sel chip-" + role;
  c.innerHTML = `<span>${esc(label)}</span><button class="x" aria-label="Remove ${esc(label)}" title="remove">&times;</button>`;
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
  renderParamCards();
  schedulePreview();
}

// Only a few capabilities take params, so this shows nothing for most routes. Collects the
// param-bearing capabilities actually on the built route (pass-through caps + the previewed
// plan's steps) and renders a typed control per param: enum/bool -> dropdown, int/float ->
// number, else text. Values live in paramVals so they survive re-renders; default is shown
// as the placeholder (omitting a value reproduces the historical behaviour).
function refineCaps() {
  const caps = new Map();
  const add = (capId) => {
    if (!capId || caps.has(capId)) return;
    const n = (DATA.network.nodes || []).find(
      (x) => x.kind === "op" && x.capability === capId && (x.parameters || []).length);
    if (n) caps.set(capId, { weaver: n.weaver, capability: capId, parameters: n.parameters });
  };
  lastParameterCaps.forEach((c) => caps.set(c.capability, c));
  build.through.forEach(add);
  if (lastRoutePath) (lastRoutePath.nodes || []).forEach((n) => { if (n.kind === "op") add(n.capability); });
  return [...caps.values()];
}

// One control's HTML for a param (value pulled from paramVals so it survives re-renders).
function paramControlHTML(capId, p, scope = "graph") {
  const v = (paramVals[capId] && paramVals[capId][p.name]) || "";
  const controlId = "param-" + scope + "-" + encodeURIComponent(capId + ":" + p.name);
  const attr = `id="${controlId}" class="rf-i" data-cap="${esc(capId)}" data-name="${esc(p.name)}"`;
  const defOpt = p.default != null ? ` (${esc(String(p.default))})` : "";
  let ctrl;
  if (p.enum && p.enum.length) {
    ctrl = `<select ${attr}><option value="">default${defOpt}</option>` +
      p.enum.map((o) => `<option value="${esc(String(o))}"${String(o) === v ? " selected" : ""}>${esc(String(o))}</option>`).join("") + `</select>`;
  } else if (p.type === "bool") {
    ctrl = `<select ${attr}><option value="">default${defOpt}</option>` +
      `<option value="true"${v === "true" ? " selected" : ""}>true</option>` +
      `<option value="false"${v === "false" ? " selected" : ""}>false</option></select>`;
  } else {
    const t = (p.type === "int" || p.type === "float") ? "number" : "text";
    const ph = p.default != null ? "default: " + p.default : "";
    ctrl = `<input ${attr} type="${t}" value="${esc(v)}" placeholder="${esc(ph)}" autocomplete="off">`;
  }
  return `<div class="rf-row"><label class="rf-l" for="${controlId}">${esc(p.name)}</label>${ctrl}` +
    (p.description ? `<div class="rf-desc">${esc(p.description)}</div>` : "") + `</div>`;
}

function bindParamControls(host) {
  host.querySelectorAll(".rf-i").forEach((inp) => {
    const cap = inp.getAttribute("data-cap"), name = inp.getAttribute("data-name");
    inp.oninput = inp.onchange = () => {
      paramVals[cap] = paramVals[cap] || {};
      if (inp.value === "") delete paramVals[cap][name];
      else paramVals[cap][name] = inp.value;
    };
  });
}

// Floating param cards, one per param-bearing capability on the route, anchored next to
// that weaver's node on the graph (positionParamCards keeps them glued on pan/zoom).
let paramCardEls = {};   // capability_id -> {el, nodeId}
function renderParamCards() {
  const host = document.getElementById("paramcards"); if (!host) return;
  const caps = refineCaps();
  const live = new Set(caps.map((c) => c.capability));
  // Drop cards no longer on the route.
  Object.keys(paramCardEls).forEach((cid) => {
    if (!live.has(cid)) { paramCardEls[cid].el.remove(); delete paramCardEls[cid]; }
  });
  // Create/refresh a card per param-bearing cap.
  caps.forEach((c) => {
    let entry = paramCardEls[c.capability];
    if (!entry) {
      const el = document.createElement("div");
      el.className = "paramcard";
      host.appendChild(el);
      entry = paramCardEls[c.capability] = { el, nodeId: "op:" + c.weaver + ":" + c.capability };
    }
    entry.el.innerHTML = `<div class="pc-h">${esc(c.weaver)} · ${esc(c.capability)}</div>` +
      c.parameters.map((p) => paramControlHTML(c.capability, p)).join("");
    bindParamControls(entry.el);
  });
  positionParamCards();
}

// Glue each card beside its node; hide when off the network view, not building, or off-screen.
function positionParamCards() {
  const L = layouts[current];
  Object.values(paramCardEls).forEach(({ el, nodeId }) => {
    const n = (buildMode && current === 0 && L) ? L.nodes.get(nodeId) : null;
    if (!n) { el.style.display = "none"; return; }
    const [sx, sy] = toScreen(n.x, n.y);
    if (sx < -260 || sx > innerWidth + 40 || sy < -40 || sy > innerHeight + 40) { el.style.display = "none"; return; }
    el.style.display = "block";
    el.style.left = Math.round(sx + (n.w * cam.scale) / 2 + 12) + "px";
    el.style.top = Math.round(sy - 18) + "px";
  });
}
function clearParamCards() {
  Object.values(paramCardEls).forEach(({ el }) => el.remove());
  paramCardEls = {};
}
function paramTick() { positionParamCards(); requestAnimationFrame(paramTick); }

function collectParams() {
  const out = {};
  const active = new Set(refineCaps().map((c) => c.capability));
  Object.keys(paramVals).filter((cap) => active.has(cap)).forEach((cap) => {
    const inner = {};
    Object.keys(paramVals[cap]).forEach((nm) => { if (paramVals[cap][nm] !== "") inner[nm] = paramVals[cap][nm]; });
    if (Object.keys(inner).length) out[cap] = inner;
  });
  return out;
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
  if (!buildMode || !build.have.length || (!build.want.length && !build.through.length)) {
    routeFocus = null; lastRoutePath = null; lastParameterCaps = []; renderParamCards(); return;
  }
  try {
    const r = await fetch("/api/plan", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(toPlanRequest(experimentState())),
    });
    const d = await r.json();
    if (seq !== previewSeq) return;                         // superseded by a newer selection
    lastParameterCaps = d.parameter_capabilities || [];
    if (!d.ok) { routeFocus = null; lastRoutePath = null; renderParamCards();
      document.getElementById("bg-hint").textContent = "No route: " + (d.error || "unavailable"); return; }
    if (!d.path) { routeFocus = null; lastRoutePath = null; renderParamCards(); return; }
    const p = d.path, idmap = {};
    (p.nodes || []).forEach((n) => { if (n.kind === "op") idmap[n.id] = "op:" + n.weaver + ":" + n.capability; });
    const nodes = new Set(), edgeKeys = new Set();
    (p.nodes || []).forEach((n) => nodes.add(n.kind === "op" ? idmap[n.id] : n.id));
    (p.edges || []).forEach((e) => edgeKeys.add((idmap[e.source] || e.source) + ">" + (idmap[e.target] || e.target)));
    routeFocus = { nodes, edgeKeys };
    lastRoutePath = p; renderParamCards();   // surface any param-bearing steps on this route
  } catch (e) { if (seq === previewSeq) { routeFocus = null;
    document.getElementById("bg-hint").textContent = "Could not preview the route: " + String(e); } }
}

// Clear all build selection + highlight state synchronously and invalidate any pending plan.
function clearBuild() {
  build.have = []; build.through = []; build.want = [];
  const v = document.getElementById("bg-value"); if (v) v.value = "";
  previewSeq++; clearTimeout(previewTimer);
  routeFocus = null; buildSel = null; lastRoutePath = null; lastParameterCaps = []; paramVals = {};
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
  previewSeq++; clearTimeout(previewTimer); closePicker(); clearParamCards();
  document.getElementById("bg-panel").style.display = "none";
  document.getElementById("b-build").textContent = "Build on the graph";
}

async function runBuild() {
  if (!build.have.length) { showError("Pick a starting type first."); return; }
  if (!build.want.length && !build.through.length) { showError("Choose outputs or a pass-through step."); return; }
  try {
    const body = toQueryRequest(experimentState());
    if (!body.batch && !Object.keys(body.have).length) { showError("Enter input values."); return; }
    await previewRoute();
    return streamRun(body, document.getElementById("bg-run"), null);
  } catch (e) { showError(String(e)); }
}

function setupBuilder() {
  if (!SERVED) return;
  document.getElementById("builder").style.display = "block";
  document.getElementById("b-runs").onclick = showSavedRuns;
  document.getElementById("b-build").onclick = () => (buildMode ? exitBuild() : enterBuild());
  document.getElementById("b-batch-file").onchange = async (event) => {
    const file = event.target.files[0]; if (!file) return;
    try {
      document.getElementById("b-batch-text").value = await file.text();
      document.getElementById("b-batch-format").value = file.name.toLowerCase().endsWith(".csv") ? "csv" : file.name.toLowerCase().endsWith(".tsv") ? "tsv" : "lines";
      document.getElementById("b-batch-enabled").checked = true;
      document.getElementById("b-progress").textContent = "Loaded " + file.name + ".";
    } catch (error) { showError("Could not read the file: " + error); }
  };
  document.getElementById("bg-run").onclick = runBuild;
  document.getElementById("bg-code").onclick = showCode;
  document.getElementById("bg-exit").onclick = exitBuild;
  document.getElementById("bg-reset").onclick = clearBuild;
  document.getElementById("bg-value").addEventListener("keydown", (e) => { if (e.key === "Enter") runBuild(); });
  // Dismiss the output picker on any outside click (capture phase: runs before the
  // canvas click that opens a new one, so opening doesn't immediately close it).
  addEventListener("click", (e) => { if (pickerEl && !pickerEl.contains(e.target)) closePicker(); }, true);
  paramTick();   // keep floating param cards glued to their nodes on pan/zoom
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
  addEventListener("keydown", (e) => {
    const sheet = document.getElementById("sheet");
    if (sheet.hidden) return;
    if (e.key === "Escape") { e.preventDefault(); closeSheet(); return; }
    if (e.key === "Tab") {
      const focusable = [...sheet.querySelectorAll("button, input, select, textarea, [href], [tabindex='0']")]
        .filter((el) => !el.disabled && el.getClientRects().length);
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  // Deep link: #have=...&want=... pre-fills and auto-plans (shareable braid).
  const m = new URLSearchParams(location.hash.slice(1));
  if (m.get("have") || m.get("want")) {
    document.getElementById("b-have").value = (m.get("have") || "").replace(/,/g, ", ");
    document.getElementById("b-want").value = (m.get("want") || "").replace(/,/g, ", ");
    runPlan();
  }
}
"""
