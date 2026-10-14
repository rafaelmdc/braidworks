# Documentation map: reader needs and Diátaxis

Mapping pass, 2026-10-14. The tables record the arrangement at review time and proposed
edits. The implementation notes below distinguish completed changes from remaining work.

Braidworks documentation should help a researcher connect the identifiers they have
to the information they need, then judge what the returned observations mean.
Contributors need reliable contracts and a safe way to extend a source.

## Method and scope

[Diátaxis](https://diataxis.fr/start-here/) distinguishes learning through practice
(tutorials), completing a task (how-to), looking up facts (reference), and understanding
relationships and reasons (explanation). Its [application guidance](https://diataxis.fr/how-to-use-diataxis/)
recommends small improvements to existing content rather than imposing empty categories.
The classifications below are our assessment of this repository.

This pass examined root documentation navigation, active guide structure, toolkit
documentation and all 17 weaver README section inventories. Close reading focused on
usage, results, persistence, database setup, pacing, configuration and implementation
guidance. This is not a fresh verification of every source assertion or live example.
Historical plans are records, not current instructions. The earlier
[accuracy pass](documentation-accuracy.md) records its separate checks.

The custom redocument-file skill guides evidence checking and preservation of useful
facts; stop-slop guides prose editing. Reader testing remains pending. Keep existing
URLs for now: an intended home identifies a reader need, not a mandatory folder.

## Active documentation map

| Existing page | Current role | Intended home and next edit |
|---|---|---|
| [Root README](../../README.md) | Introduction, first command, navigation | Entry point. Keep the connected-source example and interpretation warning; link verified lessons. |
| [Index](../index.md) | Task/audience navigation | Navigation. Distinguish learning, tasks, lookup and understanding as pages acquire those roles. |
| [Installation](../installation.md) | Several installation tasks | How-to. Preserve selected installs, isolated environment, browser extra and wheels; let a tutorial choose one setup. |
| [Usage](../usage.md) | Interface tasks, first-query fragments, expansion and controls | How-to collection. Keep CLI/Python/browser, batch, direct-source and expansion tasks findable; link full lessons. |
| [Results](../results.md) | Interpretation, export steps, exact schemas, Python outcomes and archives | Explanation + how-to + reference. Keep coverage/review prominent; give exact fields and archive guarantees a reference home. |
| [Sources](../sources.md) | Source selection, catalogue facts and local acquisition | Reference with selection guidance. Preserve biological meaning and setup constraints; link source-specific tasks. |
| [Key index](../keys-index.md) | Generated producer/consumer inventory | Reference. Preserve exact keys and generation; link route-discovery tasks. |
| [NCBI setup](../database.md) | Acquisition/use, shared generation/locking contracts, reviewed-history migration | How-to + reference. Keep consent, paths and rebuild steps; separate generic local-data contracts and NCBI history reference. |
| [Persistence](../persistence.md) | Storage choice, CLI save/resume, schemas/leases, configured Python script | How-to + explanation + reference. Keep storage-choice table near tasks; separate store contracts and configured Python task. |
| [Pacing](../request-pacing.md) | Rate-setting task, defaults/precedence, fleet coordination, adapter integration | How-to + reference. Keep rate/precedence near commands; separate integration and distributed coordination for contributors/operators. |
| [Architecture](../architecture.md) | Question-to-result story, responsibilities and boundaries | Explanation. Preserve the global model; link exact contracts rather than adding signatures. |
| [Core contracts](../core-contracts.md) | Invariants and implementation pointers | Contributor reference. Preserve batch, failure, cache and serialization guarantees. |
| [Configuration](../weaver-configuration.md) | Provider example, ownership and builder signatures | Reference with how-to fragment. Keep validated options and ownership; link a complete configured-source task. |
| [Repository structure](../repo-structure.md) | Package/code-change map | Contributor reference. Preserve workspace constraints and where-to-change lookup. |
| [Implementation guide](../weaver-implementation-guide.md) | Scaffold workflow, custom-plumbing manual and stale instructions | Contributor how-to. Repair scaffold-first path; distinguish handwritten NCBI guidance from shared runtime. |
| [Releasing](../releasing.md) | Artifact checks and publication constraints | Maintainer how-to. Preserve verification, independent versions and automated tagging. |
| [0.12 migration](../migrating-to-0.12.md), [0.13 migration](../migrating-to-0.13.md) | Version-specific upgrade steps | Version-scoped how-to. Preserve affected interfaces and before/after behavior. |
| [Writing conventions](../documentation-style.md) | Contributor writing guidance | How-to/checklist. Add purpose classification and detail-preservation checks. |
| [Core README](../../braidworks-core/README.md) | Concepts/discovery/API fragment, appended storage instructions | Package entry point. Link canonical storage guides; storage instructions currently follow the license. |
| [Toolkit README](../../weaverkit/README.md) | Scaffolding, spec reference, rationale, browser tasks/endpoints, Python API | Package entry point. Route browser users and adapter authors separately; link task/reference/explanation material. |
| [Backend implementation](../../weaverkit/docs/implementing-backends.md) | Backend contract and guidance | Contributor reference/how-to. Preserve status, batch, fingerprint and golden/live verification rules. |
| [Safe regeneration](../../weaverkit/docs/safe-regeneration.md) | Extend without overwriting implementation | How-to. Preserve scratch generation, selective copying, NCBI exception and verification. |
| [Pitfalls](../../weaverkit/docs/PITFALLS.md) | Troubleshooting and contract reminders | Contributor task support. Link authoritative contracts. |
| [Toolkit decisions](../../weaverkit/docs/decisions.md) | Rationale and dated decisions | Explanation/decision record. Verify claims before promoting them to current reference. |
| [Distributed README](../../braidworks-arq/README.md) | Architecture, worker setup, expansion/discovery/durability | Experimental entry point. Separate setup from coordination/reference; retain status and durability limits. |

The offline network HTML and machine TSV catalogue are discovery/reference artifacts.
They complement prose; they do not teach interpretation of a research result.

## Source README map

Start source pages with purpose, inputs, useful outputs, setup and a working entry
path. Keep scientific scope beside usage. Technical reference can follow or move to
linked pages; small READMEs need not be split just to satisfy categories.

| Source | Useful details to preserve | Organization target |
|---|---|---|
| [UniProt](../../weavers/uniprot_weaver/README.md) | Species constraint, representative selection, mapping directions/coverage/job limits, exact description | Group current mapping/description tasks; replace release-shaped sequencing with reference. |
| [PDBe](../../weavers/pdbe_weaver/README.md) | Experimental structure meaning, full sets vs display caps, mapping scope | Put lookup/expansion tasks before transport/resource contracts. |
| [AlphaFold](../../weavers/alphafold_weaver/README.md) | Predictions, model inventory, archive/API distinction, confidence links | Group API/archive tasks; keep prediction interpretation beside results. |
| [QuickGO](../../weavers/quickgo_weaver/README.md) | Evidence, pagination budget/completeness, hierarchy/reverse lookup | Show task entry points; keep incompleteness visible and batch mechanics in reference. |
| [Reactome](../../weavers/reactome_weaver/README.md) | Pathway/reaction evidence, full ordered sets vs capped display | Group tasks and interpretation; retain source-update contracts below. |
| [STRING](../../weavers/string_weaver/README.md) | Association meaning, species/score controls, service identity/pacing | Put interpretation/filter choices before request mechanics. |
| [NCBI](../../weavers/ncbi_weaver/README.md) | Taxonomy/gene/genome scope, backend coverage, report limits, local/history rules | Route by biological task; reserve handwritten internals for contributors. |
| [BacDive](../../weavers/bacdive_weaver/README.md) | Type-strain representative, scan limits, strain-specific evidence | Put representation/coverage caveats beside usage. |
| [Disbiome](../../weavers/disbiome_weaver/README.md) | Local acquisition, association direction, disease identity, snapshot coverage | Separate real-data setup from synthetic examples and implementation chronology. |
| [FAPROTAX](../../weavers/faprotax_weaver/README.md) | Lineage input, inferred functions, licensing, affiliation evidence | Keep NCBI-lineage task and interpretation together; place matching internals below. |
| [GMrepo](../../weavers/gmrepo_weaver/README.md) | Acquisition coverage, sample/cohort denominators, optional profiles | Lead with real-data task and denominator rules; label synthetic examples. |
| [GTDB](../../weavers/gtdb_weaver/README.md) | API/local differences, coherent release bundle, genome evidence/tree scope | Organize by task and required artifacts; place build mechanics in reference. |
| [MONDO](../../weavers/mondo_weaver/README.md) | Mapping semantics, disease identity, release-matched SSSOM, schema/rebuild requirements | Bring capability inventory forward; group current setup/reference and relocate dated narrative. |
| [Wikidata](../../weavers/wikidata_weaver/README.md) | Homonym review, rank filter, taxon identity | Keep disambiguation beside examples; consolidate shared construction/failure guidance. |
| [Wikipedia](../../weavers/wikipedia_weaver/README.md) | Attention meaning, trailing-year vs local month, language/source scope | Put measurement choice before usage; retain dump identity in reference. |
| [AGORA](../../weavers/agora_weaver/README.md) | Crosswalk vs acquired models, archive cost, reaction coverage/artifact validation | Lead with tasks/prerequisites; put build details after scientific scope. |
| [Example](../../weavers/example_weaver/README.md) | Teaching data, explicit registration, offline batch | Contributor lesson, distinct from actual researcher tutorials. |

Per-weaver CONTRIBUTING files are extension guides. IMPLEMENTATION files are scaffold
worklists whose completion state matters; review their claims when repairing the
contributor path rather than placing them in researcher navigation.

## Findings

| Priority | Concern and evidence | Impact and recommendation |
|---|---|---|
| High | No complete researcher lesson in the root reading path. README/usage contain snippets and controls, not a guided question → preparation → lookup → coverage → interpretation → export sequence. | A user can run a command without learning to judge the observations. Build three verified lessons with prerequisites, expected shapes and interpretation limits; link deeper mechanics. |
| High | Implementation guide §3 assumes single-input MVP; §6 says dispatch lives in taxon and should be copied. Core now provides `BackendDispatchWeaver`, `Capability.consumes_any` and `BackendBase.fetch`; scaffold uses them. Guide also asks for manual root lint paths, but Makefile derives weaver paths. | Contributors may duplicate machinery or follow contradicted steps. Repair scaffold-first guidance against generator/AGENTS/strict verification. Preserve custom NCBI guidance separately. This gap survived the earlier accuracy pass. |
| Medium | Results mixes interpretation/export/schema; persistence mixes CLI tasks with store revisions, leases and schemas. | Developer contracts interrupt analysis tasks. Give them linked reference homes without losing identity, review, archive or recovery guarantees. |
| Medium | NCBI setup includes generic generation/lock contracts; pacing includes adapter wiring and fleet coordination. | Different audiences interrupt each other's tasks. Keep actionable consent/path/rebuild/rate rules nearby; separate contributor/operator reference. |
| Medium | Source READMEs accumulate release-shaped sections: MONDO group-aware reads, UniProt mapping/description version headings, AGORA bounded-work sections. Core storage instructions follow license. | Readers reconstruct current behavior from patches. Group by current task/capability; preserve migration thresholds and move incidental chronology to records. |
| Medium | Toolkit README mixes scaffold/spec, TOML rationale, browser controls/endpoints and toolkit Python usage. | Browser users and adapter authors must sift unrelated material. Use a two-audience entry page and separate task/reference/explanation links. |
| Medium | Source READMEs repeat installation, lifecycle and failure guidance alongside source scope. | Boilerplate obscures source differences and risks drift. Link canonical shared facts; retain endpoint, credential, scope, snapshot and interpretation exceptions. |
| Medium | CLI facts live mostly in help; Python contracts are spread across examples and code links. | No single lookup path for exact interfaces. Add a reference landing page linking help, interfaces, configuration, keys and specs; assess generated reference separately. |
| Low | Index groups tasks/audiences without distinguishing a lesson from lookup/explanation. | Readers cannot choose by learning intent. Add Diátaxis navigation incrementally with plain task labels; do not advertise snippets as complete lessons. |

These are organization/accuracy findings, not runtime defect claims. Code-checked
implementation-guide contradictions are established; reader impacts are assessments
to validate through the joint researcher review.

## Preserve useful detail

Ask which choice, action, interpretation or recovery each section supports. Keep a
fact if removing it could change that outcome. Move it when another audience needs
it. Remove filler, duplicated facts with a canonical home, or obsolete claims only
after checking their replacements. Shorter does not automatically mean clearer.

| Near the task | In linked reference/explanation | Remove or archive after checking |
|---|---|---|
| Input/species identity, setup/download requirements, output meaning, missing/review/completeness rules | Exact schemas, TTL/lease defaults, ownership/cancellation, fingerprints/generations, provider limits, batching contracts | Slogans, vague claims, code narration, repeated boilerplate, incidental release chronology, contradicted instructions |

Coverage warnings are scientific detail. Lease semantics are operational detail.
Both matter; neither needs to appear in every first-query lesson.

## Next edits and acceptance

1. Repair the inaccurate contributor implementation path before reusing it in a lesson.
2. Develop one complete researcher lesson and its result-interpretation path. Verify
   actual routes before choosing the remaining two subjects.
3. Separate export/archive and persistence reference from tasks. Apply the same
   approach to local-data and pacing docs where it helps a concrete audience.
4. Reorganize toolkit/source READMEs by current tasks, reviewing one source at a time
   against spec/code/tests and preserving scientific limits.
5. Reflect the resulting roles in navigation. Avoid bulk URL moves; fix links and
   preserve a useful route from old locations when a move is justified.

For each rewrite, record audience/purpose, facts retained/moved/corrected and checks.
Verify links, command syntax and executable examples in an isolated environment.
Label mutable/synthetic results honestly. Runtime tests are warranted when behavior
or meaningful contracts change. Link checks do not establish scientific correctness
or readability; researcher walkthroughs test the latter.

## Records outside active reader paths

[History](../history.md) covers implementation, fan-out, GUI, local-setup and source
roadmaps. [Audits](README.md) and [refactoring records](../refactoring/README.md) retain
findings/specs/plans/validation snapshots. [Current work](../NEXT.md) and
[toolkit backlog](../../weaverkit/docs/backlog.md) track work. Keep them accessible
to maintainers but separate from current learning/task paths; retain dates/status
notices rather than promoting snapshots into current guarantees.

## First implementation increment

The contributor implementation guide now follows the spec/scaffold/backend/verification
path. It retains connectivity, groups/parameters/fan dimensions, provenance, source
identity, batch order/duplicates/bulk requests, failure/review rules, acquisition
consent and atomicity, client ownership, discovery/builders, strict goldens/live checks,
serialization and versioning. Exact backend contracts remain linked in the toolkit
reference. Removed handwritten examples described obsolete copying of dispatch,
mapper, base classes and metadata, plus single-input MVP constraints. NCBI's custom
machinery remains a separate section. No runtime code or contract tests changed.

The first [researcher tutorial](../tutorials/protein-structures.md) teaches connected
retrieval, bounded related-entity inspection, batch preparation, coverage interpretation
and export. README/index link it; navigation names learning, tasks, reference and
understanding. Two further lessons, joint reader testing, and the reference separation
and source README edits remain.

Validation used the existing isolated environment and ignored scratch directory.
Three published tutorial query commands ran against live UniProt/PDBe: two batch rows
resolved with no missing fields or review/errors; bounded expansion returned two
structure descriptions; CSV/archive contents were inspected. This checks these examples
at this time, not source availability or dataset stability. Selected package installation
passed a dry run without changing the environment. A scratch scaffold from the toolkit
fixture confirmed the shared-runtime layout and Python parsing; the implemented Example
weaver passed strict verification. Local links/anchors and whitespace were checked.
Human readability still needs a walkthrough.

## Second implementation increment

The type-specific guidance comes from Diátaxis's [tutorial](https://diataxis.fr/tutorials/),
[how-to](https://diataxis.fr/how-to-guides/), [reference](https://diataxis.fr/reference/)
and [explanation](https://diataxis.fr/explanation/) pages. We apply it here by guiding
one exercise at a time, keeping relevant task branches in how-to pages, organizing
exact contracts for lookup, and placing interpretation/reasons in explanation.

Three researcher lessons now cover proteins/structures, microbial functional-rule
traces and disease–microbe publication evidence. The protein lesson has fewer option
and explanation detours. Each lesson retains setup side effects, observable results
and scientific interpretation limits. These are working examples, not evidence that
researchers have completed a usability review.

Result and persistence details moved into [result reference](../reference/results.md)
and [storage reference](../reference/persistence.md). Retained facts include terminal
row identity/order, structured metadata, Python outcome distinctions, archive permissions,
schema and failure guarantees, cache identity/TTLs/eviction/physical size, run ownership,
lease expiry, atomic snapshots, repeated reads, schema compatibility, local-disk and
retention rules. The configured Python persistence task remains executable in the
how-to guide. A [reference index](../reference/index.md) links these and existing
interface authorities. Old results/persistence task headings remain available for links.

[Result meaning](../explanation/result-meaning.md) connects coverage, review,
representative selection, expansion and reproducibility. The practical result guide
now helps readers inspect coverage and save exports rather than mixing in whole schemas.
Spreadsheet rendering was checked against the CLI: requested list values use semicolon
separators; metadata JSON and `strands` retain structured values.

Validation: selected ecology and disease package installs passed dry runs without
changing the isolated environment. The exact ecology commands and inspection script
ran through live NCBI and bundled FAPROTAX; membership and matched-rule evidence were
checked. Real Disbiome tables were acquired into an ignored scratch database (about
45 MB SQLite); the exact lesson script reused it, checked provider disease identity,
retained faecal-sample observations/publications and exported coverage/references.
Acquisition and subsequent lookup were verified separately; this does not freeze the
provider snapshot. The relocated managed persistence script ran with PDBe. Local links
and whitespace checks passed. No runtime implementation or contract tests changed.

Remaining organization work: toolkit/source README structure, local-data and pacing
reference separation where useful, and joint researcher walkthroughs. The tutorials
are ready for that reader review; reliability against future live source changes
remains a maintenance task.
