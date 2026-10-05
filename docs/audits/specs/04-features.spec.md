# Audit 04 remediation spec

Status: audited requirements; current remediation status is in ../README.md and matching plans; evidence confidence remains as stated below. Source audit: ../reports/04-features.md. Each finding has stable ID A04-NN. Full source evidence, limitations, strengths and open questions are preserved below. This is a remediation specification, not a weaver.spec.toml or a request to weaken contracts.

## Requirements index

| ID | Requirement/problem | Status |
|---|---|---|
| A04-01 | Spreadsheet exports erase outcome status and omit fatal-only entities | fixed; core 352 passed; toolkit 178 passed; see matching plan for scope |
| A04-02 | CLI files do not carry the provenance needed to reuse a biological result | fixed for completed CLI executions |
| A04-03 | GO aggregation loses annotation evidence and exposes truncated results as ordinary counts | fixed for documented scope; see plan evidence |
| A04-04 | Symbol resolution selects a representative without a user-visible ambiguity contract | fixed for documented scope; see plan evidence |
| A04-05 | Several molecular lookup batches still make serial upstream calls | fixed for documented scope; see plan evidence |
| A04-06 | Planning documents and generated inventory lag current features | fixed for documented scope; see plan evidence |
| A04-07 | Cross-process cache/resume is a missing convenience, not a prerequisite for a small first release | deferred for first publication; scope documented |

## Preserved audit evidence

# Feature analysis and first-release scope

## Executive assessment

Braidworks already has the feature surface for a useful molecular first release. Current source specs contain **17 weavers and 33 capabilities**, including both UniProt mapping directions, alternative input routing, collection fan-out, CSV/TSV input/output, grouped fields, per-query parameters, references, and deterministic fixtures. The next release should consolidate these workflows rather than add another database or implement the already-present gene→protein bridge.

Type-level paths exist for all four requested molecular workflows. This establishes composability, not biological coverage or operational success. A dependable release requires the correctness repairs identified in audit 01 and package/release repairs in audit 02, plus preserving outcome and provenance in exported files. Small, explicitly bounded batches and structure expansion are defensible initial scope; exhaustive protein annotation, species-wide inventories, large ortholog enrichment, and distributed throughput are not established by this audit.

## Strengths worth preserving

- The registry offers independent alternative-input edges (`braidworks-core/src/braidworks/core/registry.py:117`), and UniProt's `map_to_accession` actually declares them (`weavers/uniprot_weaver/weaver.spec.toml:93`). This is already the gene→protein hinge.
- PDBe, QuickGO, and Reactome each pair an identifier-set list with a matching describe consumer; NCBI children/orthologs expose explicit same-key traversal. This is a coherent user model, not a need for new orchestration.
- UniProt ID mapping submits batches and follows result pages (`weavers/uniprot_weaver/src/uniprot_weaver/backends/api.py:319`, `:329`). STRING uses two bulk stages (`weavers/string_weaver/src/string_weaver/backends/api.py:122`). PDBe/QuickGO/Reactome describe tests assert many IDs in one request.
- Shared identifiers, grouped fields, configured versus introspection builders, and fixture-backed goldens should remain intact. An unconfigured local backend or an intentionally unproduced entry-point key is not itself a defect.
- Source records retain useful detail: STRING evidence channels, PDBe coverage/resolution, and Disbiome full joined association records. These are valuable inputs to transparent biological interpretation.

## Numbered findings

### 1. Spreadsheet exports erase outcome status and omit fatal-only entities

**Category:** release blocker for the flagship spreadsheet workflow. **Severity:** high. **Confidence:** confirmed status loss by isolated execution; fatal-row omission confirmed from source. **Effort:** S–M.

**Evidence:** `braidworks-core/src/braidworks/core/cli.py:209` creates a status field, but `:236`–`:251` writes only entity, optional parent, and requested values. `_cmd_weave` constructs records only from resolved, unresolved, and review buckets at `:365`–`:371`; errors are reported separately at `:386`. Traversed exports repeat the same bucket selection at `:458`–`:464`.

**Impact/reproduction:** Calling the unchanged `_emit` function with a resolved p53 row and an unresolved empty row produces `entity,protein.name\ne1,p53\ne2,\n`. The spreadsheet cannot distinguish review, no-match, and missing fields. An entity appearing only in errors has no data row. The stderr count/exit code is insufficient once a file is handed to a colleague.

**Smallest remedy:** Include stable status and a compact diagnostic column; emit a terminal row for each fatal-only entity without duplicating partially successful entities. Include branch completion information when a resolved entity has missing requested fields. Reuse stable accounting from audit 01 finding 4.

**Validation:** A fixture batch containing success, no-match, review, branch-local failure, and fatal failure retains every root/leaf outcome in CSV, TSV, and JSON; serialized counts agree with rows and successful values survive partial failure.

### 2. CLI files do not carry the provenance needed to reuse a biological result

**Category:** first-release improvement; required for a claim of reproducible exported results. **Severity:** high. **Confidence:** confirmed. **Effort:** M.

**Evidence:** `_record` extracts only `Strand.value` (`braidworks-core/src/braidworks/core/cli.py:208`) despite serializable confidence/provenance/metadata (`braidworks-core/src/braidworks/core/strand.py:47`). Optional references print to stderr (`cli.py:374`). Shared lookup provenance identifies weaver/backend (`braidworks-core/src/braidworks/core/mapper.py:50`), but the live UniProt fingerprint is the API-contract constant `uniprot-rest-v1` (`weavers/uniprot_weaver/src/uniprot_weaver/backends/api.py:189`), and analogous PDBe/QuickGO/Reactome constants identify interfaces rather than immutable data releases.

**Impact/reasoning:** A saved JSON/CSV file loses source attribution and effective species/filter parameters unless the user separately archives stderr and command history. Repeating a live query later can retrieve different data even with identical interface fingerprints. Deterministic fixtures and deterministic ordering do not establish historical data replay. This concerns upstream data attribution, separately from software licensing (audit 02).

**Smallest remedy:** Add an opt-in result bundle/sidecar containing effective parameters, input identity, planned and executed source/version/backend, retrieval time, available upstream release identifiers, references, branch outcomes, and full strand JSON. State when a source is live and cannot be replayed from a pinned snapshot. Repair reroute reference loss through audit 01 finding 8.

**Validation:** Archive and reload a fixture run without losing parameters, lineage, confidence, references, or completion state; a live-run bundle identifies its retrieval date and does not claim an immutable snapshot without one.

### 3. GO aggregation loses annotation evidence and exposes truncated results as ordinary counts

**Category:** first-release improvement; blocker for an exhaustive or evidence-qualified GO claim. **Severity:** high. **Confidence:** confirmed. **Effort:** M.

**Evidence:** `weavers/quickgo_weaver/src/quickgo_weaver/backends/api.py:63` deduplicates by GO ID and retains only ID/name/aspect at `:67`; `:77` counts observed distinct terms. `_all_annotations` caps pages at `:191` and only logs truncation at `:209`. The spec has no GO evidence/qualifier parameters (`weavers/quickgo_weaver/weaver.spec.toml`, `list_go_terms`).

**Impact/reasoning:** Bench users cannot tell from an exported GO list whether support was experimental or computational, or distinguish an observed subset from a complete set. The displayed count is a count within retrieved pages, not a demonstrated complete source total. Discarded evidence prevents later filtering. This audit did not verify whether negative qualifiers occur in this endpoint's default live response, so it makes no claim that a particular negative annotation currently appears as positive.

**Smallest remedy:** Export completeness/page-cap metadata; preserve evidence and qualifiers in an annotation-detail group or explicitly describe current output as deduplicated term inventory. Add declared evidence/qualifier parameters only after verifying real source fields and defaults. Keep existing `go.term` joins backward compatible.

**Validation:** A mocked response exceeding the configured page cap visibly reports incomplete coverage; two rows for one GO ID retain their distinct annotation evidence in detail output; verified source examples establish qualifier behavior before promising biological filtering.

### 4. Symbol resolution selects a representative without a user-visible ambiguity contract

**Category:** first-release improvement. **Severity:** medium–high. **Confidence:** confirmed behavior; biological suitability depends on task. **Effort:** S for clear contract and examples, M for candidate/review support.

**Evidence:** UniProt is a `lookup` (`weavers/uniprot_weaver/weaver.spec.toml:16`); `_best_hit` chooses a representative from the first nonempty reviewed-first search (`weavers/uniprot_weaver/src/uniprot_weaver/backends/api.py:374`–`:385`). Organism is optional (`weaver.spec.toml:60`). The live symbol test deliberately does not assert the human accession (`weavers/uniprot_weaver/tests/test_e2e_live.py:28`), and it calls without an organism parameter at `:34`–`:43`.

**Impact/reasoning:** A bare symbol may resolve to another species; organism-constrained symbols can still denote more than one acceptable protein. The result does not mean all isoforms or all matching proteins, and cannot be advertised as such. By contrast, ID mapping returns an explicit set with reviewed-first ordering. Audit 01's ambiguity policy defects are separate framework blockers and must be fixed before expanding resolver-style review here.

**Smallest remedy:** Lead with accessions or organism-pinned symbols; explain representative selection in the returned metadata/documentation. Add a live species-pinned TP53 known-truth test. Candidate review or a separate list capability can follow demonstrated user demand, preserving the existing lookup contract.

**Validation:** `TP53` with organism `9606` returns P04637 and human taxonomy; fixtures with multiple plausible matches expose selection basis or candidates, and never label representative selection exhaustive.

### 5. Several molecular lookup batches still make serial upstream calls

**Category:** first-release improvement; blocker for an unqualified scale claim. **Severity:** medium. **Confidence:** confirmed source behavior; throughput not measured. **Effort:** M.

**Evidence:** Await inside the per-query loop: UniProt resolution (`weavers/uniprot_weaver/src/uniprot_weaver/backends/api.py:219`), PDBe lists (`weavers/pdbe_weaver/src/pdbe_weaver/backends/api.py:139`), QuickGO lists (`weavers/quickgo_weaver/src/quickgo_weaver/backends/api.py:131`), Reactome lists (`weavers/reactome_weaver/src/reactome_weaver/backends/api.py:121`), and AlphaFold (`weavers/alphafold_weaver/src/alphafold_weaver/backends/api.py:100`). QuickGO pages and UniProt search variants can add multiple requests per query. Bulk describe and UniProt ID-mapping implementations already exist and must be preserved.

**Impact/reasoning:** A modest gene batch or ortholog fan can accumulate latency as a sum of upstream request times. Existing engine batches do not automatically make these source calls concurrent. No live load test was performed and no upstream bulk endpoint is assumed to exist.

**Smallest remedy:** Use a verified bulk source endpoint where available, otherwise bounded concurrent per-query calls with source-specific rate limits and ordered results; publish a measured small-batch limit first. Avoid treating the current arq estimated budget as actual HTTP accounting (audit 01 finding 9).

**Validation:** Controlled-delay transport proves bounded concurrency and ordered one-result-per-input behavior; bulk tests prove request counts where appropriate; small live measurements record elapsed time and errors without stressing upstream services.

### 6. Planning documents and generated inventory lag current features

**Category:** first-release improvement. **Severity:** medium. **Confidence:** confirmed. **Effort:** S.

**Evidence:** `docs/NEXT.md:23` says the gene→protein edge is missing; the current declaration is `weavers/uniprot_weaver/weaver.spec.toml:92` and async implementation is `src/uniprot_weaver/backends/api.py:310`. `docs/NEXT.md:12` claims nine weavers, versus 17 source specs. `docs/weavers-index.tsv:1` plus all its rows omit GMrepo/MONDO; those specs exist at `weavers/gmrepo_weaver/weaver.spec.toml:50` and `weavers/mondo_weaver/weaver.spec.toml:40`. `docs/demo.sh:44` calls its PDB selection “most recent”; PDBe ranks coverage/resolution/ID (`weavers/pdbe_weaver/src/pdbe_weaver/backends/api.py:50`), not release date.

**Impact/reasoning:** Maintainers can repeat shipped work or promise the wrong selection rule. Users can miss available sources. In particular a disease ontology source already exists; “add a disease hub” must be reframed as a specific missing bridge, not an absent source. Generated indexes are secondary documentation, not current capability truth.

**Smallest remedy:** Refresh NEXT/roadmap around measured workflow acceptance, regenerate published indexes as a deliberate later change, and explain actual TOP ordering. Remove dated absolute live counts from the demo.

**Validation:** Compare current discovered manifests/specs with both generated indexes; every flagship path and selection description agrees with current implementation. Do not add duplicate UniProt mapping capabilities.

### 7. Cross-process cache/resume is a missing convenience, not a prerequisite for a small first release

**Category:** later (design suggestion). **Severity:** medium for repeated large jobs, low for proposed scope. **Confidence:** confirmed default behavior; deployment-specific needs unverified. **Effort:** M–L.

**Evidence:** CLI constructs a fresh `LocalExecutor(registry)` per run (`braidworks-core/src/braidworks/core/cli.py:357`); its default cache is in memory (`braidworks-core/src/braidworks/core/executor.py:244`). CLI options at `cli.py:688`–`:705` expose expansion/parameters but no cache path or resume checkpoint. The cache protocol permits injection; no disk result cache/checkpoint implementation was identified in targeted source searches.

**Impact/reasoning:** Restarting a long interrupted CLI batch repeats completed upstream work. Local data stores are durable, but that does not preserve a job's results. Implementing persistence prematurely would also persist existing cache-coverage defects (audit 01 finding 1) and would need a freshness policy for live API-contract fingerprints.

**Smallest remedy:** For first release, document run-local caching and bounded batches, retaining input IDs/results for explicit reruns. Later add opt-in durable results and resumability keyed by validated source fingerprint, effective parameters, inputs, and execution state; do not require a distributed rewrite.

**Validation:** An interrupted fixture job resumes without duplicate completed work, invalidates when data/parameters change, and reports stale live data according to a documented refresh policy.

## Flagship reachability and acceptance scope

These paths were reconstructed from current specs with the same single-input/`consumes_any` projection as `registry.py:134`. They are **type-level reachability**, not a runtime planner/executor certification.

| Workflow | Current path | Operational/biological boundary | First-release acceptance example |
|---|---|---|---|
| Human TP53 → GO processes + partners | `protein.query` → UniProt `resolve_protein` → accession → QuickGO `list_go_terms` / STRING `list_interactions` | Pin organism=9606; representative protein, GO term inventory, STRING returned partner subset. Individual live tests exist, not a demonstrated current composed live pass. | Fixture run produces P04637, human identity, GO and scored partner records with visible status; one small live pinned run validates identity and nonempty branches without fixed counts. |
| Batch genes → spreadsheet | Same branches for each input; examples/genes.txt and examples/README.md already provide command | Files are read as a batch; current export loses outcomes and source metadata. No demonstrated safe large-job size. | 10–20 pinned human inputs including duplicate, invalid, and ambiguous examples; every input/leaf represented, lineage/status preserved, failures don't erase successful branch data. Publish observed elapsed time. |
| Accession → individual PDB descriptions | accession → PDBe `list_structures` → set `pdb.id` → PDBe `describe_structure`; UniProt `map_from_accession` is another producer | Expansion order depends on selected source; TOP is not “latest”. Missing structures are meaningful absences. Expansion bound defects from audit 01 apply. | P04637, `--expand top:5`, five-or-fewer deterministic fixture children with title/method/date and parent; bulk describe call and bounded cloning verified; tiny live check confirms returned IDs are describable. |
| Orthologs → protein annotation | gene ID → explicit NCBI ortholog traversal → gene IDs → UniProt `map_to_accession` → accession sets → existing hub branches | Same-key ortholog relationship needs traversal, not ordinary shortest-path routing. Many-to-many gene/protein mappings and sparse source coverage must remain visible; do not globally apply human organism filtering to nonhuman children. Audit 01 seed-attribute and expansion defects must be repaired. | Fixture parent 7157 → at least two species' child IDs, multi-accession and unmapped child cases; correct root lineage, no inherited TP53 attributes, explicit coverage denominators. Small live subset records mapping/annotation coverage per species before broader demo claims. |

Recommended first-release core: installable/discoverable core + toolkit and existing molecular weavers, Python API + CLI, species-pinned representative dossiers, modest batch CSV/TSV/JSON exports, bounded PDB expansion, and experimental ortholog enrichment only after composed acceptance. Existing organism/local sources may remain available as documented optional extensions; supporting 17 packages need not imply equal readiness for every data-dependent workflow.

Defer a new source catalogue, animated execution UI, species-wide protein harvesting, KEGG integration, domain/family source additions, automated biological interpretation, Redis deployment guarantees, and transparent arbitrary-size resume. Existing mappings to KEGG IDs do not supply KEGG pathway descriptions or establish permission to redistribute KEGG data. AGORA's declared `CC-BY-NC-4.0` is a distinct upstream-data constraint, not a restriction to infer for every package.

A targeted disease bridge is plausible later: Disbiome/GMrepo disease IDs live inside association dictionaries, while MONDO consumes shared disease identifiers. Current specs do not expose disease IDs as fan dimensions. Likewise MONDO produces ontology IDs/attributes, not MeSH IDs for the `gmrepo.sample_profiles` consumer. The reconstruction found no `disease.name`→sample-profile route and no `organism.name`→protein-accession route. These are task-specific gaps, not proof that disease sources or the protein hinge are absent. Add typed set outputs only after a real cross-domain task and identifier/license semantics are settled.

## Verification log

- Read root AGENTS.md, COMMON, assigned prompt, and audit 01/02; reused their established engine/package findings rather than repeating their tests. No nested AGENTS.md was identified by prior audit; no contrary nested instructions encountered.
- Parsed all 17 source specs with standard-library `tomllib`: 33 capabilities; 27 declared golden cases. Inspected shared-key registry, current generated TSV/key indexes, NEXT/roadmap/demo/examples, factories, molecular API fetch/aggregation/fingerprint implementations, and named live/bulk tests. Did not audit every source setup/parser or independently verify upstream licensing terms.
- Initial system dependency probe: `pytest=False`, `networkx=False`, `httpx=True`; no root venv initially. Parent later reported user-authorized environment setup; its full sync failed building zipfile-deflate64 because gcc/Python headers were absent. No targeted pytest or actual registry commands were run here; the coordinating audit may append recovered verification separately. No dependencies were installed by this audit agent.
- Standard-library graph reconstruction implemented the documented alternative-input projection; demonstrated all four requested molecular paths, missing organism-name→accession and disease-name→sample-profile paths, and missing GMrepo/MONDO index rows. This is not execution of the actual registry or cost-based planner.
- Executed unchanged `_cell`/`_emit` function definitions extracted from actual CLI AST in an isolated standard-library namespace. Confirmed CSV drops status for success/no-match input records. No fake biological response or copied replacement implementation was used.
- Source inventory: 14 packages have a defined fixture-suffixed builder; example/FAPROTAX use bundled deterministic local data without a separate fixture builder; 14 have test_e2e_live.py files. Presence of tests/goldens is not a pass claim. NCBI's two declared goldens cover taxonomy, not all eight capabilities; UniProt goldens cover representative resolution and into-hub mapping, while reverse mapping has dedicated mocked/live tests.
- No full suite, live APIs, data downloads, tracked index regeneration, package publication, or production edits. Only this report was written.

## Top five actions

1. Fix audited engine/package blockers first, then prove the four composed workflows against deterministic fixtures.
2. Make spreadsheet export preserve status, diagnostics, branch completeness, and every terminal entity.
3. Provide an archival result bundle with parameters, executed-source provenance, references, and retrieval identity.
4. Make GO completeness/evidence and representative protein selection explicit; validate species-pinned live TP53.
5. Publish a measured small-batch/expansion envelope; replace serial source loops with bounded concurrency or verified bulk calls before broad scale claims.

## Open questions and limitations

- What biological acceptance policy is intended for multiple proteins per gene: one representative, all mappings, or human review? Current features support sets, but scope should state the choice.
- What small-batch size/elapsed-time/error envelope is suitable for bench users? No load or current composed live coverage measurement was performed.
- Should first-release provenance be a JSON bundle, spreadsheet sidecar, or both? Preserve simple table usability while retaining an archival form.
- Current upstream availability and legal terms were not researched; NEXT's historic Reactome outage and NCBI 429 notes are not treated as current verified failures. Fixtures do not establish nonmodel organism coverage.
- Existing arq/GUI implementations were not independently audited here. This report does not claim their absence or certification.

## Compact source inventory

`F` means a defined deterministic fixture builder; `B` means bundled local data instead; `L` means an opt-in live test file exists, not that it passed. License entries are source-spec declarations, not legal verification. Capabilities default to lookup; NCBI and Wikidata are declared resolver sources.

| Source | Capabilities; current join shape | Declared backend / prerequisites | Params | Golden / fixture / live | Declared upstream license |
|---|---|---|---|---|---|
| UniProt | 3: symbol/accession text→representative; 8 alternative ID types→accession set; accession→12 xref sets | Keyless API | organism | 2 / F / L | CC-BY-4.0 |
| PDBe | 2: accession→PDB set; PDB→entity description | Keyless API | none | 2 / F / L | CC0-1.0 |
| QuickGO | 2: accession→GO set/aspects; GO→term description | Keyless API | none | 2 / F / L | CC-BY-4.0 |
| Reactome | 2: accession→pathway set; pathway→description | Keyless API | none | 2 / F / L | CC0-1.0 |
| STRING | 1: accession→partner names/records and protein.query set; no dedicated partner describe | Keyless API | none (constructor limit) | 1 / F / L | CC-BY-4.0 |
| AlphaFold | 1: accession→model attributes/URLs | Keyless API | none | 1 / F / L | CC-BY-4.0 |
| NCBI | 8: names/taxa, children, assemblies, genes, orthologs; children/orthologs self-key sets, genome list/describe pair | Local taxonomy requires DB; API, optional key; local/backend support varies per capability | rank, reference_only, annotated_only, assembly_level, taxon, taxon_filter | 2 / F / L | Public Domain |
| GTDB | 2: taxid OR scientific name→taxonomy/tree position | Local configured DB/tree; keyless API alternative | none | 3 / F / L | CC-BY-SA-4.0 |
| BacDive | 1: scientific name→strain-derived traits | Keyless API | none (configured scan cap) | 1 / F / L | CC-BY-4.0 |
| FAPROTAX | 1: NCBI lineage→functional groups | Bundled local release | none | 2 / B / — | Open |
| Disbiome | 1: species-rank taxid→disease association records | Local DB must be built | none | 1 / F / L | Open |
| GMrepo | 2: taxid→abundance associations; MeSH ID→sample profiles | Local DB; profile phenotypes/runs configured during build | none per query | 1 / F / L | Open |
| MONDO | 3: MeSH, MedDRA, disease name→ontology identity/ancestors | Local DB must be built | none | 1 / F / L | CC-BY-4.0 |
| AGORA | 1: taxid→metabolic reconstruction/reaction/model groups | Bundled crosswalk; reactions need DB, models consent-gated | none | 2 / F / — | CC-BY-NC-4.0 |
| Wikidata | 1: scientific name→candidate QID/Wikipedia title | Keyless API resolver | expected_rank | 1 / F / L | CC0-1.0 |
| Wikipedia | 1: title→pageviews | API or configured monthly local dump | none | 1 / F / L | CC0-1.0 |
| Example | 1: taxid→example traits | Bundled local demonstration data | none | 2 / B / — | CC0-1.0 |
