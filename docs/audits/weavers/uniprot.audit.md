# UniProt weaver audit

Date: 2026-10-08; source revision `d5e7543`; package `0.2.3`, core floor `0.13.0`.
Status: audited locally; recommendations proposed. No backend edits made.

## Main findings

| ID | Priority | Finding | Evidence/impact | Recommendation |
|---|---|---|---|---|
| WV-UNIPROT-001 | P1 | Reviewed preference can override an exact unreviewed accession | `_best_hit` loops reviewed status outside query specificity; fixture returns another reviewed hit before searching supplied accession unreviewed | Treat explicit accession as identity; search exact across review status before broader fallback |
| WV-UNIPROT-002 | P1 | ID mapping is neither distinct nor deterministically ordered within review classes | `_idmap` appends response order/duplicates; reproduced duplicate accessions and inflated count 3 for two IDs | Normalize distinct IDs, sort within reviewed/unreviewed classes; derive counts from normalized sets |
| WV-UNIPROT-003 | P1 | Outbound mapping violates group completeness and cache coverage | One mapping group declares 14 outputs, fetch only requested target; cached GeneID result satisfies later PDB group request without PDB lookup; count-only returns NO_MATCH | Design truthful target-specific groups/summary semantics and prove cache reuse across target changes |
| WV-UNIPROT-004 | P1 | Malformed upstream payload escapes record failure boundary | invalid JSON → JSONDecodeError; null result → AttributeError; only HTTPError caught | Validate response shape in source adapter; return explicit per-query errors for expected data failures |
| WV-UNIPROT-005 | P2 | Search 400/404 becomes ERROR contrary to repository fetch convention | Both reproduced; all HTTPError handled alike | Apply endpoint-aware status handling and repository not-found convention; retain service/job failures as ERROR |
| WV-UNIPROT-006 | P2 | Transport ownership/configuration are incomplete | Lazy AsyncClient never closed; builder drops **_config including client/base URL/concurrency; fingerprint ignores custom base URL | Explicit configured construction and owned/borrowed client lifecycle; source identity includes relevant configuration |
| WV-UNIPROT-007 | P2 | Search and mapping job orchestration share a large backend with weak isolation | submit/poll/page/search/normalize in one class; one source-db failure marks every mapping query ERROR | Compose a small mapping-job adapter with pure normalization helpers; isolate failures per source/target group |
| WV-UNIPROT-008 | P2 | Documented mapping interpretation and contributor guidance are misleading | README says reviewed-first chooses canonical and ALL fans every isoform; mappings do not guarantee either; CONTRIBUTING lists only one capability and stale force preservation advice | Correct scientific promises; document all capabilities and safe regeneration |
| WV-UNIPROT-009 | P2 | Core sequence/annotation/proteome workflows are missing | Only function text/length from search; no describe-by-accession, sequence, evidence/features or taxon→proteins capability | Prioritize exact accession description plus optional sequence/evidence outputs; consider proteome enumeration separately |
| WV-UNIPROT-010 | P2 | Verification omits adverse mapping lifecycle cases | 36 passing offline tests; mapping mocks always finish and return one page; order fixture one success/four fabricated misses | Add pagination, timeout, failed job, malformed page, duplicate/reordered rows, group/cache and distinct-ID batch cases |

001–005 are reproduced offline; 006–008/010 verified by code/document inspection.
009 is a research-backed feature proposal, not an existing correctness failure.
003 demonstrates a source grouping problem; it does not call for rewriting core cache.

## Researched workflows and capability coverage

Sources accessed 2026-10-08. The provider's [2024 proteomics training](https://www.ebi.ac.uk/training/events/uniprot-proteomics-scientists-2024/)
demonstrates identifier conversion and proteome/peptide/PTM workflows. It establishes
real training use cases, not a quantitative ranking of usage frequency. The
[Proteins API documentation](https://www.ebi.ac.uk/proteins/api/doc/) confirms available
sequence-feature, variation and proteomics data. These are a separate API family
from the current REST backend; integrating them requires explicit scope.

| Workflow | Evidence | Current support | Gap/action |
|---|---|---|---|
| Convert experimental identifiers into protein IDs and onward references | 2024 provider training; [mapping configuration](https://rest.uniprot.org/configure/idmapping/fields) | Partial: map_to/map_from, batched async jobs, alternative inputs and set outputs | Fix ordering/completeness; define multiple-input precedence and organism-aware gene-name mapping |
| Retrieve an identified protein's sequence and functional annotation | [2025 API paper](https://academic.oup.com/nar/article/53/W1/W547/8126256); live P04637 entry | Partial: representative search yields names/function/length/taxid | Add exact describe-by-accession and optional sequence/structured evidence; avoid search ambiguity |
| Retrieve proteins for an organism/proteome for dataset analysis | Provider training and API paper's proteome/GeneCentric services | Absent | Evaluate list_proteins/proteome identifiers, paginated complete sets and explicit bounds |
| Interpret peptides, PTMs or variation against protein features | Provider training; Proteins API docs | Absent | Defer specialized services until an input/output contract and user need are chosen |

The 2025 paper search-index extracts support programmatic sequence/annotation/mapping
use; full-page access was blocked by publisher/PMC delivery. UniProt help pages
returned JavaScript fallback text, so their details are not treated as read. Live
REST entry and configuration probes succeeded. No claims about market share or
the most frequent scientific workflow are made.

## Current capability matrix

| Capability | Backend/inputs | Behavior | Limits |
|---|---|---|---|
| resolve_protein | API; protein.query; optional organism taxid string | One reviewed-preferred representative from first matching 25-row page; annotation score then accession tie-break | Lookup, not candidate resolver; confidence defaults to 1; source-page boundary can affect choice |
| map_to_accession | API; eight alternative ID types | Two jobs per source DB, reviewed and all; results mapped back to each input | No organism parameter for gene symbols; multiple available input types choose mapping table's first nonblank |
| map_from_accession | API; accession | Jobs for requested targets among 12 DB mappings | All targets share one output group despite partial fetch; target iteration uses frozenset order |

Both mapping operations preserve per-input cardinality but fail to deduplicate output
IDs. Reviewed status means curation status; it is not a guarantee of a canonical
isoform, unique protein or species correctness. Source function evidence is stripped
from display text and structured evidence is not emitted; do not treat that text as
an evidence-preserving scientific annotation export.

## Architecture, OOP and functional design

Retain thin `BackendDispatchWeaver` plus neutral LookupRecord mapping. The backend
already uses constructor injection and useful pure helpers (`_extract`, `_pick`,
query variants). No new abstract weaver inheritance is justified.

The useful boundary is a composed **ID-mapping job adapter** responsible for
submission, bounded polling and paginated reads. Keep source/target ID tables and
record normalization as pure functions; make order and multiplicity explicit.
Use typed internal response shapes only where they clarify validation; any public
dataclass must round-trip JSON. A generic job framework or class per target DB is
unnecessary. Split by change reasons, not file length alone.

Error isolation should follow each source/target mapping group: a failed Ensembl job
must not overwrite successful GeneID queries. Sequential target jobs may later use
bounded concurrency; maintain pacing and no task leaks. Cancellation must propagate.
Poll timeout is approximately 60 delay intervals plus request time, not a strict
60-second total deadline. Document or use a real monotonic deadline.

## Full checklist assessment

- **Scientific correctness:** explicit ID identity, species ambiguity, mapping
  cardinality and evidence loss need attention; representative search limits already
  documented. Do not silently convert existing lookup to resolver without migration.
- **Input/output contracts:** all three capabilities and declared parameters reviewed;
  single mapping group conflates target selection and complete cacheable output.
- **Batch/transport:** maps use batched jobs; search uses bounded concurrency 4 and
  PacedHTTPClient. Mapping pagination follows Link but is untested; no page-cycle
  guard. No source retries/Retry-After policy in this backend. No full DB build/local
  backend exists; those checklist items are inapplicable.
- **Configuration/lifecycle:** zero-config always available; injected clients work
  only by manually composing a backend. Ownership/close policy absent; source contract
  fingerprint constant does not identify endpoint or upstream release. TTL is useful
  but not a scientific reproducibility guarantee.
- **Connectivity:** accession/taxid hubs and alternative ID edges are strong. Set
  outputs are present. Taxon→proteins is an extension candidate, not required to keep
  current edges useful. Registered key availability must be checked before new keys.
- **Human usability/docs:** CLI examples cover organism restriction; Python only
  constructs. Contributor capability list, expansion notes and regeneration advice
  are stale. Explain gene-name cross-species mapping and set ordering accurately.
- **Tests:** 36 passed, 8 opt-in live skipped; strict fixture gate passes. All eight
  live tests were read; no complete live suite run in this audit. Live structural
  tests cannot prove exact unreviewed-ID or group-cache correctness.
- **Licensing/provenance:** CC-BY-4.0/citation/attribution present, software MIT
  distinguished. Source release headers not captured into record evidence.

## Evidence and reproductions

[Offline probe](../reproductions/weaver_uniprot.py) reproduces 001–005 without
network access. The group probe stores the actual execute result in the public
InMemoryStrandCache; executor coverage normalization also retains triggered group
`mapping`, so its protection against unrequested *other* groups cannot fix this
within-group incompleteness. A full executor regression should be added during the
fix, not assumed covered by this lower-level reproduction.

Baseline: package Make test **36 passed/8 skipped**, strict verify passed. Small
live GETs to `https://rest.uniprot.org/uniprotkb/P04637.json` and mapping configuration
returned 200: P04637/taxid9606, sequence available; Gene_Name mapping DB present.
These validate available data/contracts, not all eight live tests or all mapping jobs.

Code: [API backend](../../../weavers/uniprot_weaver/src/uniprot_weaver/backends/api.py),
[mapping tables](../../../weavers/uniprot_weaver/src/uniprot_weaver/mapping.py),
[spec](../../../weavers/uniprot_weaver/weaver.spec.toml),
[factory](../../../weavers/uniprot_weaver/src/uniprot_weaver/factory.py),
[tests](../../../weavers/uniprot_weaver/tests/test_api.py),
[live tests](../../../weavers/uniprot_weaver/tests/test_e2e_live.py).
See [proposed spec](uniprot.spec.md) and [plan](uniprot.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.
