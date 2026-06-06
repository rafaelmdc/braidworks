# Weaver roadmap — linking organisms to function (ORDINA)

This document surveys the biological databases worth turning into Braidworks
weavers, prioritizes them for **ORDINA** (linking a prokaryote to *what it does*),
and gives a concrete "claim a weaver and build it" recipe. It is the strategic
companion to [CONTRIBUTING.md](../CONTRIBUTING.md), which has the mechanical
how-to; read this for *what to build next and why*, read that for *the exact shape*.

**ORDINA scope (decided):** prokaryotes / microbiome, **ecology- and trait-first**
(what the organism does), with molecular/genomic function (genes → proteins → GO →
pathways) captured here as **later notes** rather than first targets.

---

## 1. The linking model — everything joins on the organism

`taxonweaver` already turns a name into a stable identity:

```
organism.name ──[taxonweaver]──> ncbi.taxon.id
                                  organism.scientific_name
                                  ncbi.taxon.rank
                                  ncbi.taxon.parent_id
                                  ncbi.taxon.lineage   (ranked, [{taxid, rank, name}])
```

Every downstream weaver hangs off one of those outputs. There are exactly **two
join patterns**, and the braider chains them automatically — you declare what a
weaver consumes/produces and it finds the path:

- **Pattern A — taxid-keyed.** Consume `ncbi.taxon.id`, produce trait/function
  strands. Clean and exact. Used by genome/strain databases that record the NCBI
  taxid (Madin traits, BacDive, UniProt).
- **Pattern B — name/lineage-keyed.** Consume `organism.scientific_name` and/or
  `ncbi.taxon.lineage`, produce function strands. Used by databases annotated
  against *taxonomic clades at any rank* (FAPROTAX matches a lineage like
  `…;Methanobacteriaceae;Methanobrevibacter` to functions). `taxonweaver` already
  emits the scientific name and the full ranked lineage, so this needs no new core
  work.

The payoff is composition. A single plan resolves all the way from a raw name to
ecological function:

```
organism.name
   └─[taxonweaver]→ ncbi.taxon.id + lineage
        ├─[traitweaver]→   microbe.trait.oxygen, .metabolism, .temperature_optimum, …
        └─[faprotaxweaver]→ microbe.ecology.functional_groups  (e.g. methanotrophy, nitrogen_fixation)
```

This means new weavers should **consume taxonweaver's outputs, not raw names** —
let the resolver own identity, and inherit its caching, fuzzy matching, and review
handling for free.

---

## 2. Priorities for ORDINA

Ranked by *directness to ecological function* × *openness/effort* (open license +
bulk download + taxid/lineage key = cheap and high-value).

| Tier | Weaver (source) | Function spectrum | Join key | Access | License | Why this rank |
|---|---|---|---|---|---|---|
| **P0** | `traitweaver` — [bacteria-archaea-traits / Madin 2020](https://github.com/bacteria-archaea-traits/bacteria-archaea-traits) | Phenotype + growth + environment (14 phenotypic, 5 genomic, 4 environmental traits) | **NCBI taxid** | Bulk CSV (figshare + GitHub) | **CC BY** | Open, taxid-keyed, bulk → reuses our local-build + `ensure` pattern almost verbatim. The anchor trait weaver. |
| **P0** | `faprotaxweaver` — [FAPROTAX](https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/lib/php/index.php) | Ecological/metabolic **functional groups** (~90: methanotrophy, N-fixation, sulfate respiration, fermentation, chemoheterotrophy, phototrophy…) | **lineage names** (Pattern B) | Small bundled text DB + rules | Academic, cite | Highest "organism → ecological function" signal — *exactly* ORDINA's goal. Tiny data; can ship inside the package. |
| **P1** | `bacdiveweaver` — [BacDive (DSMZ)](https://bacdive.dsmz.de/) | Richest curated metabolic/physiological/ecological strain profiles (incl. enzymes via EnzymeDetector) | NCBI taxid / strain | REST API (free, **registration/key**) | Terms of use, cite | Deepest curation, but API-only + auth + rate limits; mirrors taxonweaver's `api` backend + `api_key` pattern. |
| **P1** | `gtdbweaver` — [GTDB](https://gtdb.ecogenomic.org/) | Genome-based, rank-normalized prokaryote **taxonomy bridge** | taxid ↔ GTDB id | Bulk taxdump-format files ([gtdb-taxdump](https://github.com/shenwei356/gtdb-taxdump)) | CC BY-SA | Near-free: GTDB ships **taxdump-format** files, so it can reuse `build_taxonomy_database` directly. Normalizes lineages → better trait/FAPROTAX hits. |
| **P2** | `protraitsweaver` — [ProTraits](http://protraits.irb.hr/data.html) | 424 traits × 3,046 species, text-mined + comparative genomics, **with precision scores** | species name | Bulk download | Open | Broad but noisier; the per-trait precision scores map cleanly onto Braidworks' confidence/review model. |
| **P2** | `macadamweaver` — [MACADAM](https://macadam.toulouse.inrae.fr/) | Metabolic **pathways** per taxon | taxonomy | Bulk/web | Academic | Pathway-level bridge between traits and the molecular route. (Also note [Omnicrobe](https://omnicrobe.migale.inrae.fr/) for habitats/phenotypes.) |
| **P3 (later notes — molecular/genomic)** | `uniprotweaver` — [UniProt](https://www.uniprot.org/) | taxid → proteome → proteins; **GO terms, EC numbers, keywords** | **NCBI taxid** (`organism_id:`) | REST API + bulk | CC BY 4.0 | The gateway from organism to *molecular* function; open and taxid-queryable. Start here when ORDINA grows beyond traits. |
| **P3 (later notes)** | `goweaver` — [GO / QuickGO + GOA](https://www.ebi.ac.uk/QuickGO/) | Gene Ontology terms & annotations (ontology + evidence) | UniProt/gene id, taxid | REST + bulk | Open (CC BY) | Pairs with `uniprotweaver` to attach function ontology terms. |
| **P3 (later notes — ⚠ licensing)** | KEGG | Pathways, modules, orthology (KO), EC | gene/KO | API + FTP | **Not open** | Flag: API is **academic-only, ≤3 req/s**; bulk FTP needs a **paid subscription**; commercial use needs a license. Prefer Reactome / Rhea / MetaCyc (each with their own caveats) before committing to KEGG. |

Also worth a mention when the molecular route matures: InterPro/Pfam (protein
families/domains), STRING (interactions), Reactome (pathways), Rhea (reactions),
BRENDA (enzymes).

**Build order recommendation:** `traitweaver` → `faprotaxweaver` (these two
deliver ORDINA's core organism→ecology mapping with open, low-effort data) →
`gtdbweaver` (cheap, improves the first two) → `bacdiveweaver` (depth) → the rest
as needed. Defer the entire P3 molecular block until the trait layer is in use.

---

## 3. Proposed vocabulary (strand type IDs)

Keep core domain-neutral; each weaver defines its own `vocab.py` (like
`taxonweaver/src/taxonweaver/vocab.py`). Suggested namespaces so weavers compose:

**Consumed (already produced by `taxonweaver`):**
`ncbi.taxon.id`, `organism.scientific_name`, `ncbi.taxon.rank`, `ncbi.taxon.lineage`.

**Produced — traits (`traitweaver`, `bacdiveweaver`, `protraitsweaver`):**

| type_id | example value | group |
|---|---|---|
| `microbe.trait.oxygen` | `aerobe` \| `anaerobe` \| `facultative` \| `microaerophile` | `traits.core` |
| `microbe.trait.metabolism` | `methanogen`, `chemoheterotroph`, … | `traits.core` |
| `microbe.trait.gram_stain` | `positive` \| `negative` | `traits.core` |
| `microbe.trait.cell_shape` | `rod`, `coccus`, `spiral` | `traits.core` |
| `microbe.trait.motility` / `.sporulation` | `bool` | `traits.core` |
| `microbe.trait.temperature_optimum` / `.temperature_range` | `°C` | `traits.growth` |
| `microbe.trait.ph_optimum` / `microbe.trait.salinity_optimum` | number | `traits.growth` |
| `microbe.trait.habitat` | controlled tags | `traits.ecology` |
| `microbe.trait.genome_size` / `microbe.trait.gc_content` | number | `traits.genomic` |
| `microbe.trait.pathogenicity` | controlled tag | `traits.ecology` |

**Produced — ecological function (`faprotaxweaver`):**

| type_id | example value |
|---|---|
| `microbe.ecology.functional_groups` | `["methanotrophy", "nitrogen_fixation", "chemoheterotrophy"]` |

Use **output groups** (like taxonweaver's `core` / `lineage`) so the cache stores
partial computation: requesting any `traits.growth` output computes that whole
group, and a later `traits.core` request is served from the same cached entry.
Where a source gives a confidence/precision (ProTraits, FAPROTAX rule strength),
populate the `WeaveResult` score and let low-confidence land in `review_queue`
rather than silently asserting — consistent with the framework's contract.

**Produced — molecular (later notes only):** `protein.uniprot.accession`,
`go.term` (`{id, aspect, evidence}`), `enzyme.ec`, `pathway.id`.

---

## 4. How to contribute a weaver

Follow CONTRIBUTING.md's 7-step recipe (`Adding a new weaver`) — neutral
intermediate → one mapper → backends → `BackendDispatchWeaver` → two-layer factory
glue → contract tests. `taxonweaver/` is the reference implementation. This section
adds the **ecology-weaver specifics** and the conventions we've since standardized.

**Per-weaver layout** (mirror `taxonweaver/`):

```
<name>weaver/
  pyproject.toml          depends on braidworks-core (workspace); add to root members
  Makefile                weaver-specific macros: test, test-live, ensure, lint, fmt
  src/<name>weaver/
    vocab.py              strand type_ids + capabilities + manifest builder
    intermediate.py       neutral dataclass your backends normalize into
    mapper.py             intermediate -> WeaveResult (single source of strand shape)
    weaver.py             BackendDispatchWeaver subclass
    dispatch.py / factory.py / provider.py
    backends/
      local.py            bulk file -> SQLite (Pattern A: taxid index; Pattern B: lineage index)
      api.py              REST backend (httpx, injectable client for MockTransport tests)
    setup.py              (if it has a local DB) ensure_<name>_db(...) — copy taxonweaver/setup.py
  tests/                  unit + contract mixins + an opt-in live E2E (BRAIDWORKS_RUN_LIVE)
```

**Reuse what taxonweaver already proved out:**

- **Local DB acquisition.** If the source ships a bulk file, copy the
  `taxonweaver/src/taxonweaver/setup.py` pattern: `ensure_<name>_db(path, auto=, refresh=)`
  with default-path resolution (`BRAIDWORKS_DATA_DIR` / platformdirs cache),
  consent gate (`auto=` / `BRAIDWORKS_AUTO_DOWNLOAD`), checksum verify, atomic
  build→rename, lock, disk precheck, and a `<tool> ensure` CLI subcommand. For
  `gtdbweaver`, the source is **taxdump-format**, so you can reuse
  `taxonomy_resolver.build.build_taxonomy_database` directly.
- **API backend.** Mirror `datasets_v2.py`: injectable `httpx.AsyncClient` (so
  tests drive an `httpx.MockTransport`), `api_key`/registration where required
  (BacDive), batched requests with paging, INFO logging for network use.
- **Backend choice = data shape.** Bulk + permissive license → `local` first
  (Madin, GTDB, FAPROTAX). API-gated → `api` (BacDive). Most useful weavers offer
  both, `local`-preferred, exactly like taxonweaver.
- **Contract tests.** Subclass `WeaverOrderContractTests` and
  `CacheFingerprintTests` from `braidworks.testing.contract` once per backend, plus
  an opt-in live E2E gated by `BRAIDWORKS_RUN_LIVE=1` (see
  `taxonweaver/tests/test_e2e_live.py`).

**Acceptance checklist** (a weaver is "done" when):

- [ ] Added to root `pyproject.toml` `members` and has its own `Makefile`.
- [ ] `vocab.py` defines type_ids, capabilities, and output groups; **consumes
      taxonweaver outputs** (taxid and/or scientific_name + lineage), not raw names.
- [ ] One mapper is the single source of strand shape across all backends.
- [ ] Failures are values (`NO_MATCH`); low confidence → `review_queue`; only
      structural problems raise (`BackendConfigurationError`).
- [ ] Contract mixins green for every backend; data round-trips `to_json`/`from_json`.
- [ ] If it has a local DB: `ensure_*` + `<tool> ensure` CLI, and DB artifacts are
      git-ignored (never commit multi-GB data).
- [ ] `make -C <name>weaver test` green; live E2E self-skips without the env gate.
- [ ] Licensing/attribution recorded in the weaver README (critical for BacDive,
      KEGG, FAPROTAX).

---

## 5. Sources

- bacteria-archaea-traits / Madin 2020 — [GitHub](https://github.com/bacteria-archaea-traits/bacteria-archaea-traits), [Open Traits Network](https://opentraits.org/datasets/madin-2020.html), [Scientific Data paper](https://www.nature.com/articles/s41597-020-0497-4)
- FAPROTAX — [overview & application study (MDPI)](https://www.mdpi.com/2076-3417/11/2/688), [microbetag module notes](https://microbetag.readthedocs.io/en/latest/modules/modules.html)
- BacDive — [BacDive in 2022 (NAR)](https://academic.oup.com/nar/article/50/D1/D741/6414049), [site](https://bacdive.dsmz.de/)
- GTDB — [gtdb-taxdump (trackable TaxIds)](https://github.com/shenwei356/gtdb-taxdump), [GTDB (NAR)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8728215/), [gtdb_to_taxdump](https://github.com/nick-youngblut/gtdb_to_taxdump)
- ProTraits — [landscape of microbial phenotypic traits (NAR)](https://academic.oup.com/nar/article/44/21/10074/2290929), [data portal](http://protraits.irb.hr/data.html)
- MACADAM — [MACADAM database (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6487390/)
- UniProt — [website API (NAR)](https://academic.oup.com/nar/article/53/W1/W547/8126256), [api docs](https://www.uniprot.org/api-documentation)
- KEGG licensing — [Licensing FAQ](https://www.pathway.jp/en/licensing_faq.html), [API terms](https://www.kegg.jp/kegg/rest/), [FTP](https://www.kegg.jp/kegg/download/)
