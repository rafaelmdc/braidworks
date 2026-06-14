# Weaver roadmap — linking organisms to function (ORDINA)

This document surveys the biological databases worth turning into Braidworks
weavers, makes them **reachable from one another** (each weaver's consumed/produced
strands + the shared keys that bridge databases), prioritizes them for **ORDINA**
(linking a prokaryote to *what it does*), and gives a "claim a weaver and build it"
recipe. It is the strategic companion to [CONTRIBUTING.md](../CONTRIBUTING.md),
which has the mechanical how-to.

**ORDINA scope (decided):** prokaryotes / microbiome, **ecology- and trait-first**
(what the organism does), with molecular/genomic function (genes → proteins → GO →
pathways) captured here as **later notes** rather than first targets.

**Naming rule:** name a weaver after its **database**, not the concept it serves —
`bacdive_weaver`, `gtdb_weaver`, `uniprot_weaver`. Concept names (the old
"trait_weaver") are ambiguous: "trait" can mean a dozen things, and two databases
may both be about traits. The DB name is unambiguous and tells a contributor
exactly which source and license they're dealing with.

---

## 0. Current priority & deferred breadth (2026-06)

The protein hub is built out (uniprot → pdbe / alphafold / quickgo / reactome /
string), each `list_*` set key has its `describe_*` consumer, and cardinality
fan-out ships. The next investment is **depth-for-everyone, not breadth**: a
first-class `braidworks` **CLI** (query + inspect from bash) so researchers can use
the whole network without writing Python. Weaver breadth is **deferred below it**.

Deferred-breadth weavers/capabilities (valuable, but each only deepens one corner —
pick up after the CLI):

- **`uniprot resolve_mapping`** — accession → cross-reference ids (KEGG, InterPro,
  Pfam, Ensembl, …). Turns UniProt into the intermediate edge that unlocks the
  islands below.
- **`string → KEGG`** — STRING maps proteins to KEGG pathways; a `pathway.kegg.id`
  producer (needs the KEGG-licensing note, §7).
- **Disease / MeSH hub** — STRING (and others) are disease-queryable; a
  `disease.*` / MeSH key would bridge phenotype ↔ molecular. Biggest new surface,
  least defined — design before building.

---

## 1. Reachability — how weavers connect

The braider plans multi-hop paths automatically: **a weaver is reachable iff some
registered weaver produces a strand type it consumes.** So "making weavers reach
each other" is entirely a matter of documenting each weaver's interface precisely
and agreeing on **shared key types**. Get the keys right and the graph wires itself.

### Universal join keys (the bridges)

| Entity | Key strand type | Bridges these databases |
|---|---|---|
| Organism | `ncbi.taxon.id` (taxid) | NCBI Taxonomy, GTDB, UniProt, BacDive, Disbiome, STRING, Ensembl, MGnify |
| Organism (by clade) | `organism.scientific_name` + `ncbi.taxon.lineage` | FAPROTAX, MACADAM (annotated against taxonomic clades, not taxids) |
| Protein | `protein.uniprot.accession` | UniProt ↔ GO, KEGG, InterPro, Pfam, STRING, PDB, Reactome, Rhea, BRENDA |
| Gene | `gene.ncbi.id` / `gene.ensembl.id` | NCBI Gene, RefSeq, Ensembl, UniProt |
| Chemical | `chem.chebi.id` | ChEBI ↔ Rhea ↔ KEGG compound ↔ PubChem; BacDive metabolites |
| Reaction / pathway | `reaction.rhea.id`, `pathway.reactome.id`, `pathway.kegg.id` | Rhea, Reactome, KEGG, MetaCyc |
| Function / ontology | `go.term`, `enzyme.ec` | GO/GOA, UniProt, BRENDA, KEGG |

`taxid` is the anchor for ORDINA (organism layer); `protein.uniprot.accession` is
the anchor for the molecular layer; **UniProt is the hinge** that connects the two
(it is taxid-queryable *and* cross-references nearly every molecular database).

### Two kinds of weaver: terminal vs. intermediate

- **Terminal weavers** produce the answer you actually want (ecological function,
  a trait, a GO term). E.g. `faprotax_weaver`, `bacdive_weaver`, `disbiome_weaver`.
- **Intermediate weavers** exist to *translate one key into another* so a terminal
  weaver downstream becomes reachable. E.g. a `uniprot_weaver` operation
  `taxid → protein.uniprot.accession`, or `accession → {go.term, enzyme.ec,
  pathway.kegg.id, …}` (UniProt's cross-references). These are the **edges** of the
  graph; without them the molecular databases are islands. Many weavers are both
  (UniProt is terminal for "keywords/GO" and intermediate for "give me accessions
  to hand to STRING").

Design implication: when adding a hub database, expose its **ID cross-references as
their own capability/output group**, so it can act as an intermediate. That single
choice is what lets the braider plan e.g.
`organism.name → taxid → uniprot.accession → string.interaction`.

### Weaver interface table (what each needs → offers)

| Weaver (DB) | Consumes | Produces | Role |
|---|---|---|---|
| `ncbi_weaver` (NCBI Taxonomy) | `organism.name` | `ncbi.taxon.id`, `organism.scientific_name`, `ncbi.taxon.rank`, `ncbi.taxon.parent_id`, `ncbi.taxon.lineage` | source of identity |
| `gtdb_weaver` (GTDB) | `ncbi.taxon.id` / name | `gtdb.taxon.id`, `gtdb.lineage` (rank-normalized) | intermediate (taxonomy bridge) |
| `faprotax_weaver` (FAPROTAX) | `organism.scientific_name` + `ncbi.taxon.lineage` | `microbe.ecology.functional_groups` | **terminal (ecology)** |
| `bacdive_weaver` (BacDive) | `organism.scientific_name` | `microbe.trait.*` (+ `enzyme.ec`, `chem.chebi.id` as later expansion) | terminal + intermediate |
| `disbiome_weaver` (Disbiome) | `ncbi.taxon.id` | `microbe.disease.associations` (disease + Elevated/Reduced direction, per sample/host) | **terminal (host–disease)** |
| `uniprot_weaver` (UniProt) | `ncbi.taxon.id` → / `protein.uniprot.accession` → | `protein.uniprot.accession`; `go.term`, `enzyme.ec`, `gene.*`, `pathway.kegg.id`, `pdb.id` (xrefs) | **hinge** (intermediate + terminal) |
| `go_weaver` (GO/QuickGO) | `protein.uniprot.accession` / `ncbi.taxon.id` | `go.term` (`{id, aspect, evidence}`) | terminal (ontology) |
| `string_weaver` (STRING) | `protein.uniprot.accession` (+taxid) | `string.interaction` (partners + scores) | terminal (networks) |
| `interpro_weaver` (InterPro/Pfam) | `protein.uniprot.accession` | `protein.interpro.id`, `protein.pfam.id` (families/domains) | terminal + intermediate |
| `reactome_weaver` / `rhea_weaver` | `protein.uniprot.accession` / `enzyme.ec` | `pathway.reactome.id` / `reaction.rhea.id` | terminal (pathways/reactions) |
| `chebi_weaver` (ChEBI) | `chem.chebi.id` / name | chemical descriptors, `reaction.rhea.id` xrefs | intermediate (chemistry) |

---

## 2. Priorities for ORDINA

Ranked by *directness to ecological function* × *openness/effort* (open license +
bulk download + taxid/lineage key = cheap and high-value).

> **Dropped: dedicated trait databases.** `bacdive_weaver` (shipped) already
> provides curated phenotypic traits per organism, so a standalone trait weaver
> would largely duplicate it. The candidates that did this — **Madin /
> bacteria-archaea-traits** and **ProTraits** — are therefore off the roadmap.
> (If a *taxid-keyed, aggregate-across-strains* trait source is later wanted,
> revisit them — they differ from BacDive's type-strain MVP — but that is an
> expansion of `bacdive_weaver`, not a separate weaver. See its CONTRIBUTING.md.)

| Tier | Weaver (source) | Function spectrum | Join key | Access | License | Why this rank |
|---|---|---|---|---|---|---|
| **P0** | `disbiome_weaver` — [Disbiome](https://disbiome.ugent.be/) | **Microbe ↔ disease** associations: per disease, abundance Elevated/Reduced vs healthy controls (human host; MedDRA-coded). **Must expose the full record** — quantitative values, method/sample/host, disease detail, organism detail, and the complete publication + study-quality metadata (see §4) | **NCBI taxid** (`organism_ncbi_id`) | Keyless JSON API (`disbiome.ugent.be:8080`); whole-table GETs (~7 MB total) = de-facto dump → build a small **local** SQLite (no separate dump file) | Open, cite [BMC Microbiol 2018](https://bmcmicrobiol.biomedcentral.com/articles/10.1186/s12866-018-1197-5) (confirm terms) | **Top priority.** taxid-keyed → reachable straight from `ncbi_weaver` (same pattern as BacDive); keyless; small. Adds the host-health dimension to "what does this organism do." |
| **P0** | `faprotax_weaver` — [FAPROTAX](https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/lib/php/index.php) | ~90 ecological/metabolic **functional groups** (methanotrophy, N-fixation, sulfate respiration, fermentation, phototrophy…) | **lineage names** | Small bundled text DB + rules | Academic, cite | Most direct "organism → ecological function" signal — *exactly* ORDINA. Tiny data; ship in-package. |
| **P1** | `gtdb_weaver` — [GTDB](https://gtdb.ecogenomic.org/) | Genome-based, rank-normalized **taxonomy bridge** | taxid ↔ GTDB id | Bulk taxdump-format ([gtdb-taxdump](https://github.com/shenwei356/gtdb-taxdump)) | CC BY-SA | Near-free: ships **taxdump-format** files → reuse `build_taxonomy_database` directly. Better lineages → better FAPROTAX hits. |
| ✅ shipped | `bacdive_weaver` — [BacDive (DSMZ)](https://bacdive.dsmz.de/) | Richest curated metabolic/physiological/ecological strain profiles | **scientific name** (type strain) | REST API v2 (free, **no key**) | CC BY 4.0, cite | Deepest curation; shipped 0.1.0 (type-strain MVP). Also an intermediate (→ ChEBI, BRENDA, ENA) once those xrefs are emitted. |
| **P2** | `macadam_weaver` — [MACADAM](https://macadam.toulouse.inrae.fr/) | Metabolic **pathways** per taxon | taxonomy | Bulk/web | Academic | Bridges traits ↔ the molecular route. (Also [Omnicrobe](https://omnicrobe.migale.inrae.fr/) for habitats/phenotypes.) |

**Build order:** `bacdive_weaver` ✅ done → `disbiome_weaver` (**top priority** —
taxid-keyed, keyless, host-disease signal) → `faprotax_weaver` (open, low-effort,
ORDINA's core ecological signal) → `gtdb_weaver` (cheap, sharpens lineage-keyed
hits) → P2 as needed. Defer the molecular block (§3) until the trait/ecology layer
is in use.

---

## 3. The versatile hubs (top molecular databases — later notes)

The most-used, most-cross-referenced biological databases. They are mostly the
**molecular** route (P3 for ORDINA), but they're listed because they interlink
densely — adding any one makes several others reachable through shared keys, and
they're how ORDINA would later go from organism → genes/proteins → mechanism.

| Weaver (DB) | What it is | Join key(s) | Access / license | Connects to |
|---|---|---|---|---|
| `uniprot_weaver` — [UniProt](https://www.uniprot.org/) | Universal protein knowledgebase (the hinge) | taxid (`organism_id:`), accession | REST + bulk, CC BY 4.0 | GO, KEGG, InterPro, Pfam, STRING, PDB, Reactome, Rhea, BRENDA |
| `go_weaver` — [GO / QuickGO + GOA](https://www.ebi.ac.uk/QuickGO/) | Gene Ontology terms + annotations | accession, taxid, `go.term` | REST + bulk, open | UniProt, BRENDA, KEGG |
| `ncbigene_weaver` — [NCBI Gene / RefSeq](https://www.ncbi.nlm.nih.gov/gene) | Genes & reference sequences | `gene.ncbi.id`, taxid | E-utils + bulk, public domain | UniProt, Ensembl |
| `ensembl_weaver` — [Ensembl (Bacteria)](https://bacteria.ensembl.org/) | Genomes, genes, comparative | `gene.ensembl.id`, taxid | REST + bulk, open | UniProt, STRING |
| `string_weaver` — [STRING](https://string-db.org/) | Protein–protein interaction networks (5,000+ organisms) | accession/Ensembl + taxid | REST + bulk, CC BY 4.0 | UniProt, Ensembl |
| `interpro_weaver` — [InterPro / Pfam](https://www.ebi.ac.uk/interpro/) | Protein families & domains | accession | REST + bulk, open | UniProt |
| `kegg_weaver` — [KEGG](https://www.kegg.jp/) | Pathways, modules, orthology (KO), EC | KO, EC, gene | API + FTP, **NOT open** ⚠ | UniProt, GO |
| `reactome_weaver` — [Reactome](https://reactome.org/) | Curated pathways | accession, `pathway.reactome.id` | REST + bulk, CC0 | UniProt, ChEBI |
| `rhea_weaver` — [Rhea](https://www.rhea-db.org/) | Biochemical reactions | `reaction.rhea.id`, EC, ChEBI | REST + bulk, CC BY 4.0 | UniProt, ChEBI, KEGG |
| `chebi_weaver` — [ChEBI](https://www.ebi.ac.uk/chebi/) | Chemical entities | `chem.chebi.id` | REST + bulk, CC BY 4.0 | Rhea, KEGG, PubChem, BacDive |
| `brenda_weaver` — [BRENDA](https://www.brenda-enzymes.org/) | Enzyme functional data | EC, accession | SOAP/REST, **registration** | UniProt, GO |
| `pdb_weaver` — [PDB / PDBe](https://www.ebi.ac.uk/pdbe/) | 3-D structures | `pdb.id`, accession | REST + bulk, CC0 | UniProt |
| `mgnify_weaver` — [MGnify](https://www.ebi.ac.uk/metagenomics/) | Metagenomics / microbiome analyses | taxid, sample, MAG | REST + bulk, open | NCBI, GTDB |

> ⚠ **KEGG licensing gotcha:** the API is **academic-only, ≤3 req/s**; bulk FTP
> needs a **paid subscription**; commercial use needs a license. Prefer the open
> alternatives (Reactome CC0, Rhea CC BY, UniProt, GO) before committing to KEGG.

**Picking the "first molecular weaver" (when ORDINA gets there):** `uniprot_weaver`,
unquestionably — it's taxid-queryable (reachable straight from `ncbi_weaver`) and
its cross-references make GO, InterPro, STRING, PDB, Reactome and Rhea all reachable
in one more hop. Build it as both terminal (keywords/GO) and intermediate (emit
accessions + xref ids).

---

## 4. Proposed vocabulary (strand type IDs)

Each weaver owns its `vocab.py` (see `weavers/ncbi_weaver/src/ncbi_weaver/vocab.py`). Keep
core domain-neutral. Group outputs (like ncbi_weaver's `core`/`lineage`) so the
cache stores partial computation.

- **Identity (ncbi_weaver):** `ncbi.taxon.id`, `organism.scientific_name`,
  `ncbi.taxon.rank`, `ncbi.taxon.lineage`; **(GTDB)** `gtdb.taxon.id`, `gtdb.lineage`.
- **Traits:** `microbe.trait.oxygen` (`aerobe|anaerobe|facultative|microaerophile`),
  `.metabolism`, `.gram_stain`, `.cell_shape`, `.motility`, `.sporulation`,
  `.temperature_optimum`/`.temperature_range`, `.ph_optimum`, `.salinity_optimum`,
  `.habitat`, `.genome_size`, `.gc_content`, `.pathogenicity`.
- **Ecological function:** `microbe.ecology.functional_groups`
  (`["methanotrophy", "nitrogen_fixation", …]`).
- **Host–disease (Disbiome) — expose EVERYTHING:** the weaver must surface *every*
  Disbiome field, not just the direction. `microbe.disease.associations` is a list
  with one entry per experiment for the taxid, each carrying the full joined record:
  - *experiment:* `qualitative_outcome` (Elevated/Reduced), `subject_value`,
    `control_value`, `ratio`, `response_name`, `response_unit`, `control_name`,
    `method_name`, `sample_name`, `host_type`, `meddra_level`, `meddra_id`.
  - *disease* (join `/disease` by `disease_id`): `name`, `stage`, `meddra_id`,
    `meddra_level`, `abbreviations`.
  - *organism* (join `/organism`): `scientific_name`, `ncbi_id`, `incertae_sedis`,
    `silva_accession_number_base`.
  - *publication* (join `/publication` by `publication_id`): `title`, `first_author`,
    `outlet`, `volume`, `issue`, `start_page`/`end_page`, `year_of_publication`,
    `pubmed_url`, `doi`, **plus the ~16 study-quality flags** (`age_of_subjects_given`,
    `controls_matched_for_possible_confounding_factors`,
    `measure_of_variance_reported`, …) — keep all of them.

  Implementation note — **prefer a `local` backend** (like ncbi_weaver). There is
  no separate dump *file* (the site's "Export" is a client-side json→csv of the
  current view), but the API serves each table **whole in one GET**, and the entire
  dataset is tiny — **~7 MB** total (`/experiment` ~5.8 MB / 10.9k rows, `/publication`
  ~1.2 MB, `/organism` ~241 KB, `/disease` ~60 KB, `/sample`+`/method` ~7 KB). So the
  build step is "fetch the 6 endpoints once," join them, and write a small SQLite via
  `braidworks.core.localdb.ensure_local_db` (the callback-shaped plumbing ncbi_weaver
  uses — far lighter here: ~7 MB of JSON, not a 70 MB taxdump → 1.2 GB DB). Disbiome
  exposes no release tag, so derive `fingerprint()` from a **content hash** of the
  fetched tables (never `"unknown"`). An `api` backend (live fetch-all + in-memory
  join) is a fine alternative/fallback. Organisms are often genus-level and one taxid
  has many experiments → collection output. Consider grouped capabilities (`core` =
  direction + disease; `provenance` = publication + study-quality flags) so callers
  can request the lighter slice.
- **Molecular keys (hubs):** `protein.uniprot.accession`, `gene.ncbi.id`,
  `gene.ensembl.id`, `go.term`, `enzyme.ec`, `pathway.kegg.id`,
  `pathway.reactome.id`, `reaction.rhea.id`, `chem.chebi.id`,
  `protein.interpro.id`, `protein.pfam.id`, `pdb.id`, `string.interaction`.

Where a source gives confidence (FAPROTAX rule strength, fuzzy name matches),
populate the `WeaveResult` score; low confidence → `review_queue` rather than
silent assertion — consistent with the framework contract.

---

## 5. Repository organization (done)

Weavers live under `weavers/` and are picked up by a glob member, so the root stays
legible and a new weaver needs no root edit:

```
braidworks/
  braidworks-core/
  weaverkit/
  weavers/
    ncbi_weaver/
    example_weaver/
    bacdive_weaver/
    …
  docs/  Makefile  pyproject.toml
```
```toml
[tool.uv.workspace]
members = ["braidworks-core", "weaverkit", "weavers/*"]
```

The root `Makefile` auto-discovers `weavers/*/Makefile` (test, lint), so a scaffolded
weaver is built with no manual wiring. See [repo-structure.md](repo-structure.md)
for the full current layout.

---

## 6. How to contribute a weaver

Follow CONTRIBUTING.md's 7-step recipe (`Adding a new weaver`); `ncbi_weaver/` is
the reference implementation. This section adds the conventions we've since
standardized and the ecology-weaver specifics.

**Reuse what ncbi_weaver proved out:**

- **Local DB acquisition.** Bulk-file sources: copy
  `weavers/ncbi_weaver/src/ncbi_weaver/setup.py` — `ensure_<db>_db(path, auto=, refresh=)`
  with default-path resolution (`BRAIDWORKS_DATA_DIR` / platformdirs cache),
  consent gate (`auto=` / `BRAIDWORKS_AUTO_DOWNLOAD`), checksum verify, atomic
  build→rename, lock, disk precheck, and a `<tool> ensure` CLI subcommand. For
  `gtdb_weaver`, the source is **taxdump-format** → reuse
  `taxonomy_resolver.build.build_taxonomy_database` directly.
- **API backend.** Mirror `datasets_v2.py`: injectable `httpx.AsyncClient` (tests
  drive `httpx.MockTransport`), `api_key`/registration where required (e.g.
  BRENDA — BacDive's v2 API needs none), batched + paged requests, INFO logging
  for network use.
- **Backend = data shape.** Bulk + permissive → `local` (GTDB, FAPROTAX);
  API-only → `api` (BacDive); offer both where possible, `local`-preferred.
- **Be a good graph citizen.** Consume the **shared key types** from §1 (taxid;
  scientific_name + lineage; uniprot.accession), never raw names. Expose any ID
  cross-references as their own output group so the weaver can act as an
  intermediate.
- **Contract tests.** Subclass `WeaverOrderContractTests` and
  `CacheFingerprintTests` once per backend, plus an opt-in live E2E gated by
  `BRAIDWORKS_RUN_LIVE=1` (see `ncbi_weaver/tests/test_e2e_live.py`).

**Acceptance checklist** (a weaver is "done" when):

- [ ] DB-named package added to workspace `members`; has its own `Makefile`.
- [ ] `vocab.py` defines type_ids, capabilities, output groups; **consumes shared
      keys** (§1), not raw names; documents `Consumes → Produces` (add a row to §1's
      interface table).
- [ ] One mapper is the single source of strand shape across all backends.
- [ ] Failures are values (`NO_MATCH`); low confidence → `review_queue`; only
      structural problems raise.
- [ ] Contract mixins green per backend; data round-trips `to_json`/`from_json`.
- [ ] Local DB (if any): `ensure_*` + `<tool> ensure`; DB artifacts git-ignored.
- [ ] `make -C <path> test` green; live E2E self-skips without the env gate.
- [ ] Licensing/attribution in the weaver README (critical: BacDive, KEGG,
      FAPROTAX, BRENDA).

---

## 7. Sources

- Disbiome — [BMC Microbiology 2018](https://bmcmicrobiol.biomedcentral.com/articles/10.1186/s12866-018-1197-5), [site](https://disbiome.ugent.be/), JSON API at `https://disbiome.ugent.be:8080/experiment` (also `/disease`, `/organism`, `/sample`, `/method`, `/publication`)
- FAPROTAX — [application study (MDPI)](https://www.mdpi.com/2076-3417/11/2/688), [microbetag notes](https://microbetag.readthedocs.io/en/latest/modules/modules.html)
- BacDive — [BacDive 2022 (NAR)](https://academic.oup.com/nar/article/50/D1/D741/6414049), [site](https://bacdive.dsmz.de/)
- GTDB — [gtdb-taxdump](https://github.com/shenwei356/gtdb-taxdump), [GTDB (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8728215/), [gtdb_to_taxdump](https://github.com/nick-youngblut/gtdb_to_taxdump)
- MACADAM — [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6487390/); Omnicrobe — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9858090/)
- UniProt — [website API (NAR)](https://academic.oup.com/nar/article/53/W1/W547/8126256), [api docs](https://www.uniprot.org/api-documentation)
- STRING — [STRING 2023 (NAR)](https://academic.oup.com/nar/article/51/D1/D638/6825349)
- KEGG licensing — [Licensing FAQ](https://www.pathway.jp/en/licensing_faq.html), [API terms](https://www.kegg.jp/kegg/rest/), [FTP](https://www.kegg.jp/kegg/download/)
- Hubs — [QuickGO](https://www.ebi.ac.uk/QuickGO/), [InterPro](https://www.ebi.ac.uk/interpro/), [Reactome](https://reactome.org/), [Rhea](https://www.rhea-db.org/), [ChEBI](https://www.ebi.ac.uk/chebi/), [BRENDA](https://www.brenda-enzymes.org/), [PDBe](https://www.ebi.ac.uk/pdbe/), [MGnify](https://www.ebi.ac.uk/metagenomics/)
