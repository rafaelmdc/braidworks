# Individual weaver audit synthesis

Date: 2026-10-08. **All 17 audit sets complete locally**: seventeen reports, proposed
specifications and matching plans, covering 33 declared capabilities. S01–S03 done;
S04 scope review pending. **No proposed runtime changes implemented.** Branch
`audit/individual-weavers`, programme [#147](https://github.com/rafaelmdc/braidworks/issues/147).
[All source documents](README.md), [capability/interface inventory](coverage.md),
[122 finding records with classifications and acceptance links](findings.tsv).

Existing architecture is largely suitable: sixteen sources use thin shared dispatch
with composed source backends; NCBI's custom review-rich runtime remains justified.
Most urgent work concerns identity, coverage, source validation and build safety.
Design patterns should support those boundaries, not turn every weaver into a hierarchy.

## Inspectable results by source

| Weaver | Most consequential findings | Research-backed capability direction | Evidence limits |
|---|---|---|---|
| [Example](example.audit.md) | Unsafe regeneration instructions; silent config; incomplete teaching examples | Complete offline teaching workflow, no biological expansion | Bundled fixture, external research inapplicable |
| [UniProt](uniprot.audit.md) | Exact accession can lose to broad reviewed hit; duplicates and false mapping-group completeness | Exact accession description, sequence/annotation evidence | Offline reproductions; small REST observations, paper full access blocked |
| [PDBe](pdbe.audit.md) | Limit/source identity and malformed response handling | Chain/residue mapping and structure quality detail | GET observation; multi-chunk issue direct-backend only at current batch size |
| [AlphaFold](alphafold.audit.md) | F1 selection loses fragment coverage; malformed responses | Model list/coverage/confidence/PAE references | Nine-entry P04637 observation; long-fragment fixture |
| [QuickGO](quickgo.audit.md) | Singleton accepts wrong echoed protein; coverage budget missing identity | Evidence/qualifier/aspect filters and ontology relations | Raw evidence/warnings already retained; term GET only |
| [Reactome](reactome.audit.md) | Limit/source identity and parsing; narrow pathway detail | Hierarchy/participants/reaction drill-down | Protein membership GET; no enrichment certification |
| [STRING](string.audit.md) | Names collapse stable partners/species; restricted fan scope; duplicate edges/mutable version | Stable ID mapping and explicit score/network/species controls | Live ID/version observed; mixed-species bulk not tested |
| [NCBI](ncbi.audit.md) | Direct failed rebuild erases old taxa; valid build CLI crashes; requested enrichment failure hidden | Preserve resolver; historical taxids/local descendants conditional | Temp build/mock probes; no new live suite |
| [GTDB](gtdb.audit.md) | Order-dependent crosswalk; disconnected-tree distance; independently mutable release bundle | Genome identity/quality and coherent representative tree descriptor | Tiny crosswalk/tree probes; no large reference trees |
| [BacDive](bacdive.audit.md) | Genus/subspecies identity, scan exhaustion-as-absence and repeated work | Strain list/describe, culture/genome/isolation evidence | Source API current keyless contract; mocked adverse cases |
| [AGORA](agora.audit.md) | Unavailable groups falsely complete; model cache unvalidated | Model identity/drill-down and reaction/genome bridges | No real SBML/GB archive download; strict restricted-license warning |
| [FAPROTAX](faprotax.audit.md) | NCBI binomial matching and subtraction grammar incorrect | Explain putative assignments/rules after correctness | Bundled actual patterns/operators; upstream differential oracle proposed |
| [Disbiome](disbiome.audit.md) | Species-only join excludes genus entry; docs use wrong input key | Compact study evidence and disease→organism reverse bridge | Genus fixture reachability reproduced; live rank prevalence unmeasured |
| [GMrepo](gmrepo.audit.md) | Failed acquisition silently zero; cohort cap/failure context missing | Run/project/QC metadata and cohort-aware profiles | Mock build failures; no full multi-thousand-call crawl |
| [MONDO](mondo.audit.md) | Order-dependent ambiguous/nonexact mappings; cycles can stall traversal | Own-ID describe, alignment precision/obsolete status | Tiny cyclic graph safely interrupted; no new OBO build |
| [Wikidata](wikidata.audit.md) | JSON shape beyond retry handling, control literals/order/config | Stable taxon IDs/QID detail and optional language | Existing chunk/retry/rank tests good; no new live WDQS probe |
| [Wikipedia](wikipedia.audit.md) | Incomparable backend metrics, inclusive end, stale requested-month reuse | Explicit measurement scope and optional temporal series | Historical three-month GET proves inclusive bounds; no GB dump |

Workflow research uses provider tutorials/docs and database papers; it establishes
relevance without inventing usage-frequency rankings. Every real source has at least
three workflow comparisons. Reports state full-read/index-only and probe limitations.
Feature availability in an upstream service does not automatically make it accepted scope.

## Consolidated priorities and dependencies

122 rows are **finding records**, not 122 independent bugs or accepted features. Some
rows combine a shared maintenance issue with a source-specific defect/proposal. Counts:
**1 P0, 44 P1, 73 P2, 4 P3**. P0 is the reproduced direct NCBI destructive rebuild.
Specs supply acceptance criteria; plans group records into concrete work packages.

| Proposed stage | Finding/work-package references | Why/order and dependencies |
|---|---|---|
| 1. Build safety and executable build CLI | WV-NCBI-001/002, WP-NCBI-01; direct replacement WV-GTDB-005/WV-AGORA-005 | Prevent data loss first; reusing existing safe staging is smaller than a new persistence framework |
| 2. Identity and scientific interpretation | UniProt001, QuickGO001, FAPROTAX001/002, STRING001/003, GTDB001/002/003, MONDO001/002/003 | Fix wrong identities/rules/unsafe traversal before exposing more features; mapping/geometry contracts need compatibility decisions |
| 3. Explicit coverage and measurement | UniProt003, NCBI003/008, BacDive002, AGORA001/003, GMrepo001/002, Wikipedia001/002/003 | Eliminate false completed/empty results and incomparable counts; group/scope representation chosen before query docs/new outputs |
| 4. Source boundaries, configuration and lifecycle | Shared owners below plus each source's malformed payload, paging/batching/retry items | Consistent mechanisms with endpoint-aware semantics; cancellation/pacing preserved, source parsers stay local |
| 5. Documentation and maintainability | Example001/003/004/005, source config/group/source-sample/docs findings | Safe extension guidance can proceed early; final examples follow settled contracts, not abandoned behavior |
| 6. Focused capability expansions | Exact accession describe; stable STRING/strain/model/ontology/run identities; evidence and sequence references | Only accepted features; use registered keys/list→describe pairs and preserved defaults |
| Deferred research scope | Cohort statistics, full classifiers/solvers, broad graph mirrors, large downloads, cache/resume, publishing | Separate user need/input-output specification and authorization; not prerequisites for current audit completion |

These are review priorities, not authorization to implement all six stages. Existing
local plans specify validation/version updates and conditional feature steps.
Work involving simple docs/helpers is small; ambiguous contract changes, coherent release
bundles and coverage migrations are larger and should be split into reviewable commits.
No speculative completion-time estimate is presented as measured effort.

## Shared opportunities with one owner

The second pass expands these six initial workstreams to nine: semantic source
identity, stable/deterministic identity and collections, and group-aware measured
work. See [issue hierarchy and second-pass review](issue-hierarchy.md) for the
complete allocation: 81 findings primarily shared, 41 source-specific. Overlapping
concerns are cross-linked; each finding has one primary issue parent.

| Owner | Affected sources/examples | Proposed shared action and boundary |
|---|---|---|
| WV-EXAMPLE-001 | All scaffolded contributor docs; NCBI explicitly exempt | Safe scratch generation/diff/selective update instructions in template and package docs; never overwrite implemented backends |
| WV-UNIPROT-006 | Most API builders/lifecycles; source-specific configured defaults in NCBI/GTDB/BacDive/Wikipedia | Explicit accepted config and owned/borrowed client contract; semantic source settings identified, secrets excluded. Core ownership helper only if repeated implementation merits it |
| WV-UNIPROT-004 | PDBe002, AlphaFold002, QuickGO003, Reactome002, STRING006, NCBI005, BacDive003, Wikidata001, Wikipedia004 | Small composable decoding/validation/error mechanism; each source owns schema/endpoint status and per-query/chunk isolation. Never blanket 400→miss for SPARQL syntax |
| WV-NCBI-003 | UniProt003, AGORA001, GMrepo001/002 | Explicit requested-group completion/coverage. First assess existing record/warning APIs; shared extension only with concrete compatible consumers, no cache-engine rewrite |
| WV-GTDB-005 | NCBI001, AGORA005 | Safe complete replacement in public builders; reuse existing localdb staging/validation rather than parallel publish implementations |
| WV-GMREPO-006 | Local acquisition urllib loops; STRING007 source request advice | Polite acquisition budgets/pacing separate from executor-only runtime pacing; only share mechanics, source-specific defaults stay explicit |
| WV-PDBE-001 | QuickGO002, Reactome001, STRING004, GTDB004, MONDO006, Wikipedia003/006 | Effective source/release/config/resource-scope identity and validation; source-specific descriptors, reuse existing SourceBinding |
| WV-UNIPROT-002 | Exact identity, correlation, ordering/dedup and scientific selection findings across 10 sources | Shared invariants and test conventions; stable IDs, truthful ambiguity and distinct collections; selection semantics remain source-specific |
| WV-DISBIOME-002 | MONDO005, GTDB007, AGORA007, FAPROTAX006, Disbiome006 | Group-aware projection and measured performance; optional optimization follows evidence, no universal repository layer |

Per-source IDs remain stable even when linked to a shared owner. Shared issue creation
should cite all relevant IDs so implementation isn't repeated or counted as independent
infrastructure work. No new generic Repository/Factory/Strategy classes merely to match
pattern names. Pure helpers are often the smallest adequate choice.

## Compatibility decisions for review

| Decision | Recommended default | Tradeoff |
|---|---|---|
| Exact vs representative identity | Honor exact identifiers; preserve legacy representative capabilities with explicit policy; add precise describe/map paths | New ambiguous outcomes may require review where legacy lookup silently selected |
| Coverage/computed groups | Never report failed/unavailable work as completed; export partial scope honestly | Existing consumers/tests expecting silent OK may need deliberate migration |
| STRING fan identity | Add stable species-aware source bridge; retain display names as descriptive/legacy outputs | Requires downstream mapping/key registration rather than silently changing existing type |
| GTDB disconnected trees | Explicitly incomparable with tree/release identity | Existing numeric consumers must handle incompatibility; no invented maximum distance |
| MONDO mappings/names | Preserve alignment relation and candidates; exact-only default unless reviewed | Lower confident resolution can be more truthful than selecting arbitrary broader xref |
| Wikipedia metric | One explicit period/agent/project/access contract across source modes | Scalar/default migration and local multi-month availability must be specified |
| Optional expansion scope | Start with identity/drill-down/evidence for existing workflows | Statistical analysis/classification remains separately scoped |

User clarification after the audit: necessary breaking changes are permitted because
current dependent projects are owned by the user. Compatibility preservation above
is a proposed default, not a constraint: favor truthful contracts and document affected
interfaces, migrations and version updates. Optional features still need scope review.

These decisions should be made before the dependent implementation package. Credentials
or laptop-wide installs are not currently blocking the audit. The isolated environment
has include-system-site-packages=false; no full reference datasets were installed here.

## Validation and limits

All 17 cwd-correct package suites: **582 passed, 46 skipped**. All 17 strict deterministic
fixture/spec/manifest gates passed; AGORA emitted its pre-existing unknown-license
warning and remains conservatively restricted. All 17 package versions agree across
spec, pyproject and vocab. All 16 scaffolded specs compared in-memory with current generator;
NCBI custom vocabulary untouched. [Retained reproductions](../reproductions/README.md)
cover inspectable source defects without network or user-data writes.

Small live GETs checked UniProt entry/mapping configuration, PDBe summary, AlphaFold
entries, QuickGO term, Reactome membership, STRING ID/version and Wikipedia historical
bins. They are **not** full live-suite certification. Opt-in skips/access restrictions
are reported; publisher/JS/FTP limitations recorded where encountered. Browser source
integration reviewed, no per-source live browser click session claimed. No accepted
contract weakened, no production source changed, no package version bumped for docs.

Local audit commits before synthesis: `d5e7543` programme plan, `24e4426` first 4 audits,
`3e54270` next 5. Final docs/reproduction commits recorded on #147 after verification.
No push/merge/release. Next step is S04 scope review, then accepted work-package issues
and implementation one plan/package at a time on branches descending from this history.
