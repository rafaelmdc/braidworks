# What's next (start here)

Cold-start orientation for the next working session. Written 2026-06-15, after the
engine/CI hardening push (core `0.7.1`).

## Where things stand (all merged, green, tagged)

The **engine is mature**: routing, cardinality fan-out, traversal (`--for-each` /
`--traverse`), error-tolerant weaving (a node failure is branch-local + rerouted around),
interchangeable-source fallback, classified/legible errors, and the full `braidworks`
CLI. **CI is hardened**: PR lint+test, scheduled live E2E with green-lightable triage,
CodeQL, Dependabot, idempotent release tags, Node-24 actions. Nine weavers ship, plus the
offline network visualizer (`make view`) and a runnable bench-biology demo
(`docs/demo.sh`). So the next move is **reach and polish, not plumbing**.

Audience decided: **bench biologists**; the flagship is the molecular hub
(`protein.query` → UniProt → PDBe / AlphaFold / STRING / Reactome / QuickGO).

---

## ▶ Recommended next task: `uniprot resolve_mapping` (the gene→protein bridge)

**Why it's #1:** it adds the single missing edge **`gene.ncbi.id → protein.uniprot.accession`**,
which lets the ortholog fan-out flow *into* the protein hub. That upgrades the demo's third
act from "TP53's orthologs' names" to the real payoff — **"TP53 across the primates, and
here's each one's 3D structure / pathways / interactions."** It's also the long-deferred
top item on the roadmap (see [weaver-roadmap.md](weaver-roadmap.md) §0), so it does double
duty: best demo upgrade *and* clears the backlog.

**Scope:**
- New capability on `uniprot_weaver` — e.g. `resolve_mapping`: consumes `gene.ncbi.id`
  (NCBI GeneID), produces `protein.uniprot.accession`. Backed by the UniProt **ID-mapping
  REST API** (`https://rest.uniprot.org/idmapping`, `GeneID` → `UniProtKB`).
- Once that edge exists, `--for-each orthologs` → each ortholog `gene.ncbi.id` →
  `resolve_mapping` → accession → existing PDBe/AlphaFold/Reactome/STRING describes. The
  planner + fan-out compose it automatically; no new traversal needed.

**Check before committing to it (the one risk):** UniProt's ID-mapping endpoint is
**async** (submit a job, poll for results) — more involved than a single GET, and the
existing uniprot backend is synchronous search. And **coverage is sparse for non-model
orthologs** (many won't have a reviewed UniProt/PDB entry), so a 20-primate fan may return
mostly `NO_MATCH`. Probe coverage for a real ortholog set (e.g. TP53's mammalian orthologs)
**first**; if it's thin, lead the demo with the human dossier + a couple of well-covered
orthologs rather than the full fan.

---

## Then, in priority order

1. **Animate the visualizer.** It's already the pitch piece (`weaverkit view`); making a
   braid *light up as it executes* is what lands in a talk. Pure front-end, no data wiring.
2. **Breadth for cross-domain questions** — a **disease / MeSH hub** (bridge molecular ↔
   clinical) or **`string → KEGG`** (`pathway.kegg.id`, mind the KEGG-licensing note in
   roadmap §7). Each unlocks a new class of question.
3. **A second taxonomy source (Ensembl / DDBJ).** Would actually *exercise* the
   interchangeable-source reroute we built — right now nothing triggers it.

## Known issues the live E2E surfaced (small, don't forget)

- **Reactome detail endpoint is down upstream** — `describe_pathway` (`/data/query/{id}`)
  500s/404s because their Neo4j is unreachable. `list_pathways` (counts/names) is fine. The
  live triage green-lights it; monitor and re-test, or add a fallback.
- **NCBI 429s** on unauthenticated Datasets v2 — add backoff or an API key to that backend
  so live runs are cleaner (currently green-lightable, but noisy).
- **Phase-5 large-scale E2E** (from the original roadmap) was never run.

## Pointers

- Strategic roadmap + weaver catalogue: [weaver-roadmap.md](weaver-roadmap.md)
- How to add a weaver (mechanical): [../CONTRIBUTING.md](../CONTRIBUTING.md) + `make new-weaver`
- Live demo to run/show: [demo.sh](demo.sh)
- Agent memory has the full session history (traversal, error-tolerance, demo, CI efforts).
