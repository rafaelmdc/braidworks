# Individual weaver audit programme

Date: 2026-10-08. Status: planned; individual audits have not started.

## Objective and scope

Audit all 17 weaver packages individually to establish how their implementation,
data-build process, capabilities and human usability should improve. For the 16
real sources, research how people use the underlying databases and compare those
workflows with verified Braidworks support. Audit Example as a teaching package.

This programme produces evidence, specifications and implementation plans. It does
not authorize every proposed feature or start a wholesale rewrite. Complete the
audits and present their priorities before implementing the resulting plans.
Previous publication-readiness and architecture work is a baseline, not evidence
that every source-specific behavior is correct.

## Operating rules

- Follow [AGENTS.md](../../AGENTS.md); preserve conformance and strict verification.
- Evaluate current shared core dispatch and scaffolding before inventing abstractions.
  Do not presume custom implementations are wrong merely because they are custom.
- Keep biological assumptions in weavers. Propose shared changes separately, with
  concrete consumers and compatibility evidence.
- Keep existing public behavior unless a finding establishes a reason to change it.
  Identify migration costs for names, keys, outputs, defaults and saved queries.
- Use isolated tooling already available under `.audit-local`; no global installs.
  Keep scratch data and captures outside tracked files; avoid full database downloads.
- Small read-only upstream probes are allowed. Record authentication, rate limits,
  access restrictions and unavailable services rather than inventing results. Ask
  before paid access or unusually large downloads; never record credentials.
- Do not push, merge, publish or create release tags. Local documentation commits
  remain authorized. No package version bumps for audit documentation alone.
- Default to sequential audits. Do not launch new agents without authorization.
  If agents are subsequently requested, write bounded prompts first and dispatch
  at most two audits at once, retaining a review and synthesis step in this chat.
- Provide frequent progress updates describing findings, evidence and next steps.

## Documents and evidence

Use `docs/audits/weavers/` for the programme index and completed audit documents.
For each package `<source>_weaver`, create:

1. `<source>.audit.md`: researched workflows, current capability matrix, architecture
   map, findings, reproductions, limitations and cited sources.
2. `<source>.spec.md`: proposed requirements with stable IDs, intended behavior,
   compatibility constraints and explicit exclusions. Mark proposals as proposed,
   accepted, deferred or rejected; do not represent proposals as completed work.
3. `<source>.plan.md`: ordered work packages linked to requirement IDs, dependencies,
   validation, version implications and acceptance conditions.

Maintain a programme index with status, main findings, research confidence and links.
Add `summary.md` after all audits: cross-weaver comparisons, shared opportunities,
prioritized implementation order and decisions needing user input.

Use finding IDs `WV-<SOURCE>-001` onward; work packages `WP-<SOURCE>-01` onward.
Preserve IDs when findings are deferred or rejected. A shared finding has one owner
and references from affected weavers, avoiding inflated duplicate counts.

Each finding records:

| Field | Required content |
|---|---|
| Claim | Specific defect, maintenance problem or workflow gap |
| Evidence | Code path and symbol, test/probe result or cited source |
| Impact | Who is affected and a concrete example |
| Classification | Correctness, architecture, build, feature, usability, docs or tests |
| Priority | P0 incorrect/unsafe results; P1 major correctness or blocked common use; P2 worthwhile improvement; P3 optional expansion |
| Confidence | Verified, supported inference or unverified hypothesis |
| Recommendation | Smallest useful change, alternatives and cost/complexity |
| Acceptance | Observable behavior and meaningful validation |
| Decision | Proposed, accepted, deferred or rejected, with reason |

Do not give a missing feature P1 solely because an upstream endpoint exists.

## Research standard

For each real database, seek evidence for at least three representative workflows
and identify the best-supported ones. These are research targets, not a quota to
fill with speculation. If evidence is sparse, state that explicitly.

Use primary sources: official documentation/API references, provider tutorials,
database papers and published studies demonstrating actual use. Record direct URLs,
access date, publication/update date where available and the precise supported claim.
Distinguish provider-supported possibilities from demonstrated research usage.
Do not claim popularity from documentation presence, search ranking or anecdotes.

For each workflow record:

| Workflow | Evidence | Required input/output | Current support | Gap or limitation | Proposed action |
|---|---|---|---|---|---|
| Concrete research task | Direct citations | IDs, fields, filters and cardinality | Full / partial / absent / unverified | Specific missing behavior | Fix / extend / document / defer / reject |

Assess whether data are actually obtainable through the available API or downloadable
release, under usable access and licensing terms. Separate scientifically useful
features from features technically feasible in Braidworks. Retain raw sample shape
only where necessary and permitted; record versions and provenance.

## Questions answered by every audit

1. What is this source for, who uses it and which workflows have evidence?
2. What does each declared capability actually do, on each backend?
3. Do inputs, identifiers, species restrictions, output groups and parameters match
   source semantics? Are names and resolver/lookup kinds truthful?
4. Are ambiguous matches, evidence quality, missing values, duplicates, counts,
   ordering, partial coverage and truncation represented without misleading users?
5. Are source-specific parsing, transport, storage, dispatch and mapping separated
   enough to change independently? Which code already uses shared machinery?
6. Would a template method, adapter, strategy, repository or plain helper reduce a
   demonstrated problem? What is the simpler alternative and migration cost?
7. How does the implementation differ from a fresh scaffold, and which differences
   are necessary? Are generated vocab/spec/manifest/version sites consistent?
8. Are batching, pagination, bounded concurrency, pacing, timeout/retry and failure
   handling correct? Does response mapping preserve input identity and duplicates?
9. Are local data builds reproducible, streamed where appropriate, validated and
   indexed? How do source releases, checksums, atomic replacement, interrupted
   builds, connections and fingerprint invalidation work?
10. Do local/API backends offer equivalent semantics where promised? What is genuinely
    unavailable, and is that communicated rather than silently falling back?
11. Can capabilities connect through shared keys, alternative inputs and complete
    fan-out sets? Are common list/describe or identifier-mapping workflows missing?
12. Can a human configure and run representative tasks in Python, CLI and browser?
    Are installation, credentials, data preparation, examples and limits discoverable?
13. Do fixtures, golden examples, batch tests, conformance and live tests demonstrate
    real behavior? What failures or schema drift could the suite currently miss?
14. Which improvements are worth implementing, in what order, and which should wait?

## Audit procedure for one weaver

### 1. Establish the baseline

Read the spec, package metadata, manifest/vocabulary, factory, weaver dispatch,
backends, build/download commands, tests and user/contributor documentation.
Record the repository revision, package/core-floor versions and external source
version assumptions. Inventory every capability, backend and configuration path.
Run the package suite through its cwd-correct Make target and strict verification
with the deterministic fixture where available. Record failures and skips honestly.

### 2. Research workflows and source contracts

Browse primary sources using the research standard. Inspect API/bulk schema,
identifier conventions, licensing, lifecycle, authentication and request limits.
Draft the workflow matrix before recommending features.

### 3. Trace and probe behavior

Trace representative supported workflows from input through fetch/parse/map to output.
Include missing inputs, ambiguous results, duplicates, multi-input batches, output
selection, parameters and list completeness as applicable. Reproduce suspected
defects using deterministic fixtures or small scratch probes. Use a bounded live
known-truth probe where it resolves uncertainty; record network failures separately
from product failures. Avoid mistaking a mocked response for upstream evidence.

Compare local and API paths where present. Inspect cache fingerprints and source
replacement behavior without reopening the already-completed cache/resume programme
unless concrete source-specific evidence exposes a new problem.

### 4. Assess architecture and build design

Draw a small responsibility map and compare to current generated scaffolding in a
scratch destination. Never run regeneration over an existing source package during
an audit. Never regenerate NCBI's handwritten vocabulary.

For each proposed pattern, show the current pain, proposed boundary, concrete change,
compatibility risks and why a helper or existing shared API would not suffice.
Retain custom code when it has a justified contract; consult the existing
[NCBI dispatch assessment](../refactoring/ncbi-dispatch-assessment.md).

### 5. Produce a reviewable audit, spec and plan

Complete all three documents. Lead the report with a findings table and capability
coverage matrix. Separate observed defects from feature ideas. Put requirement IDs
and acceptance conditions in the spec; put ordered, commit-sized changes in the plan.
Mark any architectural recommendation dependent on later cross-weaver evidence.
Update the programme index and summarize results to the user before the next audit.

## Execution order and initial investigation targets

These targets guide investigation; they are not established defects or promised
features. Finish each audit's documents before moving to the next source.

| Order | Weaver | Initial investigation target | Status |
|---|---|---|---|
| 01 | Example | Scaffold conventions, extension instructions and teaching fidelity | Planned |
| 02 | UniProt | Search ambiguity, identifier mapping jobs, annotation coverage and hub connectivity | Planned |
| 03 | PDBe | Structure discovery/details, protein coverage and experimental metadata | Planned |
| 04 | AlphaFold | Prediction retrieval, versions, confidence interpretation and model coverage | Planned |
| 05 | QuickGO | Annotation evidence, filtering, pagination and ontology term semantics | Planned |
| 06 | Reactome | Pathway membership, hierarchy, species mapping and evidence | Planned |
| 07 | STRING | Identifier resolution, interaction evidence, networks and score meaning | Planned |
| 08 | NCBI | Taxonomy/review, datasets, gene/genome workflows and justified custom dispatch | Planned |
| 09 | GTDB | Release builds, taxonomy crosswalks and tree placement semantics | Planned |
| 10 | BacDive | Strain identity, trait evidence, batch support and access requirements | Planned |
| 11 | AGORA | Reconstruction identity, model access, release builds and model contents | Planned |
| 12 | FAPROTAX | Taxonomic inference, coverage and uncertainty of functional assignments | Planned |
| 13 | Disbiome | Association direction, study evidence, identifiers and disease drill-down | Planned |
| 14 | GMrepo | Cohort/sample metadata, abundance interpretation and phenotype linkage | Planned |
| 15 | MONDO | Ontology builds, crosswalk ambiguity, synonyms and hierarchy semantics | Planned |
| 16 | Wikidata | Taxon identity, query behavior, sitelinks and evidence/provenance | Planned |
| 17 | Wikipedia | Title/language identity, pageview dimensions, time coverage and redirects | Planned |

Example establishes the scaffold baseline. The protein/annotation group then tests
shared API conventions and connected workflows; NCBI and local-data sources exercise
mixed dispatch and build pipelines. Disease and knowledge sources complete the
cross-domain comparison. If evidence warrants reordering, record the reason.

## Programme stages and checkpoints

| Stage | Deliverable | Completion condition |
|---|---|---|
| S01 preparation | This plan; programme index and source inventory when execution starts | All 17 packages accounted for; document conventions fixed |
| S02 individual audits | 17 reports, 17 proposed specs, 17 matching plans | Every question addressed or explicitly inapplicable/unverified |
| S03 synthesis | Summary, dependency map and consolidated findings table | Shared recommendations supported by concrete cases; duplicate findings linked |
| S04 scope review | Ordered implementation backlog and explicit deferred list | User can inspect evidence, costs and compatibility decisions before implementation |
| S05 implementation, subsequently authorized | One accepted work package at a time | Meaningful checks and evidence recorded; local commits and issue mapping |
| S06 final acceptance | Integrated verification and updated capability/documentation matrices | Accepted requirements verified; omissions explicit; delivery still separately authorized |

Summarize progress after Example, after the six protein/annotation sources, after
NCBI plus the four following microbial sources, and after the remaining sources.
These checkpoints support steering; they do not require interrupting ordinary audit
work for approval. Stop for genuinely necessary credentials or decisions and continue
independent work where possible.

## Issue, branch and implementation handoff

The current branch is `refactor/persistence-foundations`; earlier completed work
remains unpushed. Create `audit/individual-weavers` from the current local HEAD when
recording this new programme, retaining all previous work without merges. Keep this
stage's documentation on that branch. Future implementation branches should descend
from that local history rather than duplicating earlier changes.

When audit execution starts, create a dedicated programme issue. After a report is
reviewed, create a per-weaver tracker and actionable implementation issues for its
accepted work packages before coding them. Link finding/requirement IDs, acceptance
criteria and dependencies. Use separate shared-infrastructure issues where needed.
Record local commit hashes and verification on issues; distinguish implemented
locally from remotely delivered. Do not close delivery trackers solely on local work.
Do not repurpose the completed earlier programme's trackers for this new scope.

Implementation plans must cover package version sites and core floors, generated
vocabulary handling, deterministic regression tests, strict verification, and live
E2E after changes to any API backend. Run lint and affected package suites per change;
reserve broad workspace/artifact/minimum-floor validation for shared changes and final
acceptance. Rebuild catalogs when manifests change. Keep data artifacts uncommitted.

## Audit completion checklist

- All 17 packages have an evidence-backed report and matching proposed spec/plan.
- All 16 real databases have cited workflow research with current-support comparison.
- Every declared capability and backend is accounted for, including unavailable paths.
- Architectural recommendations identify concrete benefits and simpler alternatives.
- Local data build/update behavior is reviewed wherever applicable.
- Findings include inspectable evidence, severity, confidence and acceptance criteria.
- Shared findings, dependencies, compatibility risks and deferred ideas are explicit.
- The summary gives a practical implementation order without pretending all useful
  upstream functionality belongs in Braidworks.
- Baseline failures/skips and inaccessible upstream checks remain visible.
- No source implementation has been changed merely to complete an audit.
