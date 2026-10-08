# GMrepo weaver audit

Date: 2026-10-08; revision `d5e7543`; package 0.2.2/core floor 0.13.3.
Status audited locally; proposals only.

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-GMREPO-001 | P1 reproduced/code | Failed taxon/profile fetch exceptions silently discarded; failed taxon yields successful overview with zero associations, no coverage/error | Persist acquisition outcome manifest and distinguish unavailable from observed empty |
| WV-GMREPO-002 | P1 code | Profile cap/failed/unrequested phenotype coverage not exported; n_runs counts only returned rows' run IDs, no cohort denominator | Export requested/selected/fetched/failed/empty run counts and cap, explicit cohort scope |
| WV-GMREPO-003 | P2 reproduced/code | Run IDs not deduplicated; DB has no uniqueness keys for taxon/phenotype/run/rank, ordering lacks full tiebreak | Stable dedup/correlation, logical keys and row order with rank; do not double count repeated pages |
| WV-GMREPO-004 | P2 reproduced/code | Numeric normalization accepts NaN/inf/out-of-range abundance/prevalence, int conversion may fail | Validated finite units/ranges/counts, raw invalid evidence distinguished from missing |
| WV-GMREPO-005 | P2 verified | No project/sample/QC/host metadata with profiles; MeSH IDs buried in leaf association records | Conditional list_runs→describe_run/profile with cohort filters and disease bridge |
| WV-GMREPO-006 | P2 code | Thousands of urllib acquisition calls bypass core runtime pacing, eight workers and no explicit retry/call budget; refresh needed to add profiles replaces whole build | Configured polite acquisition policy/coverage; separate profile resource stages, incremental extension only if reviewed |
| WV-GMREPO-007 | P2 verified/code | README has no capability/output table/full Python execution, contributor/spec samples stale endpoints, sample_profiles omitted there; config kwargs ignored; light group computes all rows | Accurate source/sample/build docs and group cost; shared safe-regeneration/config owners |

001 reproduced with two overview taxa and one failed endpoint: failed taxon found=True,
count0/no error. 002 is code inspection, not a completed live failed cohort. Existing
SourceBinding protects local generation, content hash covers profiles and build_id changes
on rebuild: do not claim same-file regenerated data is currently undetected.

## Research/workflow matrix

Primary sources accessed2026-10-08:
[original paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6943048/),
[v3 database paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12807640/),
[provider project/run docs](https://evolgeniusteam.github.io/gmrepodocumentation/websiteandUI/projectandrunpages/),
[programmable access](https://github.com/evolgeniusteam/GMrepoProgrammableAccess/blob/master/README.md).
Indexed primary texts describe metadata-aware cohort selection and cross-dataset markers;
current website reports v3 expansion. Old example endpoints are not live guarantees.

| Workflow | Current coverage | Gap/decision |
|---|---|---|
| Summarize genus/species prevalence and relative abundance by phenotype | Local overview/association DB | Acquisition coverage, finite numeric/denominator/unit provenance |
| Retrieve sample-by-taxon profiles for a phenotype | Separate optional bounded crawl | Cohort selection/cap/failure metadata, stable runs and sampled scope |
| Compare projects/case-control cohorts with confounders/QC | Not represented in output | Optional run/project details and filters using observed current endpoints |
| Explore reproducible disease markers across datasets | Summary/profile substrate, no marker capability | Conditional provider marker retrieval; statistical modeling belongs downstream |

Relative abundances are compositional measurements; profile rows alone cannot establish
causal effects, unbiased prevalence or validate co-occurrence. Avoid inventing controls
or treating missing acquisitions as zero abundance. No frequency rankings asserted.

## Complete checklist

- **Capabilities/connectivity:** local list_abundances consumes generic taxid (genus
  and species), three groups; sample_profiles consumes MeSH, one leaf matrix output.
  No params/fan identifiers. Source IDs exist inside outputs but don't route downstream.
- **Architecture/OOP:** thin shared runtime/SourceBinding/read session useful. Split
  source acquisition adapter, pure normalization and coverage-bearing build manifest;
  composed summary/profile resources suit differing cost/scope better than a backend
  subclass per phenotype or generic clinical core types. No forced repository layer.
- **Functional/build:** source coercion/helpers small and testable but over-tolerant
  shapes silently empty. Current build materializes normalized tables and future list;
  measures before streaming redesign. Consent/lock/headroom/atomic publication present.
  Validation requires hash and associations or profiles, ignoring coverage completeness.
- **Batch/errors:** query batch off event loop, duplicates repeat SQL; acquisitions
  concurrently complete unordered then deterministic primary sorts in hash, but duplicate
  equal-key ordering still source-dependent. Malformed shape/errors swallowed by workers.
- **Groups/cache/provenance:** summary loads full association views; profile availability
  absent per-phenotype manifest; requested outputs can truthfully describe available subset
  only if scope supplied. Fixed profile build config affects produced content but retrieval
  needs explicit scope regardless of content hash. Missing phenotypes not proof of absence.
- **Docs/usability:** setup/default-cache/custom location/profile refresh instructions
  good; hardcoded old phenotypes/ByMeshID source_sample mismatches current implemented
  taxon-centric source. Capture fresh bounded real source samples before implementation.
- **Tests/releases:** 25 passed,2 skipped; strict passed. Existing bounded live mini-build
  design appropriate, not run here. Add failed acquisition/capped/duplicate/empty runs,
  invalid numbers, source-shape drift and logical uniqueness. Keep contracts intact.

Offline `.audit-local/gut-weavers-probe.py` verifies silent failed taxon, duplicate run
list and NaN acceptance. [Setup](../../../weavers/gmrepo_weaver/src/gmrepo_weaver/setup.py),
[backend](../../../weavers/gmrepo_weaver/src/gmrepo_weaver/backends/local.py),
[spec](../../../weavers/gmrepo_weaver/weaver.spec.toml).
No full crawl/new live probes. [Spec](gmrepo.spec.md), [plan](gmrepo.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.

[Retained offline reproduction](../reproductions/weaver_gut_sources.py) runs without network;
all database writes stay in temporary directories.
