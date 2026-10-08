# GTDB weaver audit

Date: 2026-10-08; source revision `d5e7543`; package 0.2.3, core floor 0.13.3.
Status audited locally; proposed changes only.

## Findings

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-GTDB-001 | P1 reproduced | Crosswalk chooses first equal-priority taxonomy per taxid; shuffled two representative genomes produce different species, despite deterministic comment | Preserve genome-level alternatives or define explicit stable representative/ambiguity policy; never call many-to-one translation authoritative |
| WV-GTDB-002 | P1 reproduced | API accepts unrelated search results when exact species absent; first representative/row becomes confident lookup | Require exact identity or expose resolver candidates with review; stable accession tiebreak |
| WV-GTDB-003 | P1 reproduced/inference | `cophenetic` sums depths of disconnected bacteria/archaea trees and calls that the right maximally distant answer; tiny fixture cross-tree0.02 can be smaller than within-tree distance | Return explicit incomparable result/error for disconnected trees; attach tree/release identity and verify compatibility |
| WV-GTDB-004 | P1 code | Crosswalk and two trees acquired independently through mutable latest; release metadata fetched separately/custom URLs can be labeled with live release | Pin a coherent release bundle with observed manifests/checksums and source provenance |
| WV-GTDB-005 | P2 reproduced | Direct build upserts without clearing old rows; rebuild with new taxid leaves old taxid under new release | Stage complete replacement and validate schema/counts, preserve existing target on failure |
| WV-GTDB-006 | P2 reproduced/code | Newick accepts trailing garbage, NaN, negative lengths and empty text; download validity only nonempty | Validate parser completion/finite distance assumptions, source tree syntax and leaf coverage before publication |
| WV-GTDB-007 | P2 code | Claimed streaming setup materializes every metadata row, then builds multiple dictionaries and all leaf root paths in RAM | Stream ingestion/reduce intermediate copies, measure bounded representative build and tree costs before redesign |
| WV-GTDB-008 | P2 verified/code | Ignored builder kwargs, ineffective configured-builder guard, tree-only flags dropped; API client unclosed/static endpoint identity; gathers unbounded distinct names | Reference shared config/lifecycle owner; validate selection and bound API concurrency |
| WV-GTDB-009 | P2 verified | README omits tree usage/limits; stale force-regeneration instructions; absent representative accession/quality/synonym/release outputs | Safe extension docs plus focused genome/release metadata proposal |

003 mathematical mismatch is verified for synthetic disconnected trees; primary docs
confirm distinct reference trees, not a calibrated bridge between their roots. Do not
claim a new universal numerical distance. Current source binding already detects changed
DB/tree files and requires reopen; preserve that protection. 005 is the direct builder;
`ensure_gtdb_db` safely builds into a fresh staged target and does not retain old rows.

## Research and workflow coverage

Primary sources accessed2026-10-08:
[GTDB FAQ](https://gtdb.ecogenomic.org/faq),
[downloads](https://gtdb.ecogenomic.org/downloads),
[tree browser](https://gtdb.ecogenomic.org/tree),
[GTDB-Tk classification](https://ecogenomics.github.io/GTDBTk/commands/classify.html),
[classify workflow](https://ecogenomics.github.io/GTDBTk/commands/classify_wf.html).
Indexed official documentation supports these tasks, not quantitative popularity.

| Workflow | Current support | Gap/decision |
|---|---|---|
| Compare NCBI organism label with genome-based GTDB taxonomy | Taxid/name→one lineage | Translation can merge/split taxa; preserve genome accession, alternatives and release |
| Find representative genomes and genomic quality/metadata | Internal representative accession retained, not emitted | Conditional genome.accession input/output bridge and quality detail |
| Inspect phylogenetic relationships of species representatives | Local rootpath and pair reducer | Same-tree/release compatibility; representative lookup is not placement of a novel genome |
| Track names/synonyms/classification changes across releases | Release stored privately | Optional source release/synonym/change metadata with observed samples |
| Classify a user's MAG/genome using ANI/markers/placement | Absent | GTDB-Tk computation is separate, expensive; import its output or bridge later, do not embed classifier |

GTDB is bacteria/archaea-focused; no promise to describe arbitrary eukaryotic taxids.
FAQ explicitly explains there is no direct taxon-to-taxon translation and that releases
provide synonym data. Interpret species representative geometry accordingly.

## Complete checklist

- **Manifest/connectivity:** two max50 lookup capabilities with alternative NCBI
  taxid/scientific-name inputs. Taxonomy local/API, placement local-only correctly
  declared. No params/fan set; GTDB taxon output can be a higher rank when species
  missing, so its name must not imply universally species-level identity.
- **OOP/build design:** thin shared dispatch and source-specific backends already fit.
  SourceBinding read session/component invalidation is useful existing composition.
  Introduce source-local release-bundle descriptor/validation and crosswalk policy,
  not a core biological repository or a template hierarchy for two operations.
- **Functional design:** taxonomy parsing and tree geometry are pure and testable.
  Separate validated tree representation/compatible-path reducer from IO and release
  handling. Deterministic candidate reduction must include accession/taxonomy keys.
  `_Node` is private; no new public dataclass requirement unless adding path descriptors.
- **Build/local parity:** consent, lock, headroom and atomic setup present; direct
  upsert, nonempty-only trees, separate latest files and materialized rows are gaps.
  API name-only cannot implement authoritative taxid crosswalk; docs acknowledge this.
  Validator checks populated taxon table but not complete species/meta schema.
- **Correctness/failure:** source API gather turns raised malformed payload errors
  into per-query ERROR (better than other raw escape cases); valid wrong-shaped dict
  with absent rows may become miss. Input duplicates reused, output order retained.
  API search only first100 results; nonexact selection must not silently imply coverage.
- **Tree performance:** recursive parser/walk builds a path copy per node/leaf; existing
  contributor doc reports previous real-tree testing, not a new live audit assurance.
  No full trees downloaded here; measure memory/time before index/precomputation choice.
- **Groups/cache/provenance:** taxonomy values map groups, source-bound local identity
  includes files; geometry outputs omit identity needed when consumers mix results
  from releases/tree order. API static contract identity is not a frozen release.
- **Docs/tests/releases:** version sites consistent, tests48 passed/2 skipped and
  strict goldens passed. Existing tree-change reopen test important. Add crosswalk
  shuffle/conflict, replacement, source bundle mismatch, invalid tree, disconnected
  reducer and nonexact API cases. Existing contract tests remain intact.

## Evidence

[Offline probe](../reproductions/weaver_gtdb.py) reproduces crosswalk order dependence,
stale direct rebuild rows, invalid Newick acceptance, disconnected distance and unrelated
API selection. No large downloads/live GTDB suite run. Source:
[taxonomy](../../../weavers/gtdb_weaver/src/gtdb_weaver/taxonomy.py),
[tree](../../../weavers/gtdb_weaver/src/gtdb_weaver/tree.py),
[setup](../../../weavers/gtdb_weaver/src/gtdb_weaver/setup.py),
[API](../../../weavers/gtdb_weaver/src/gtdb_weaver/backends/api.py),
[factory](../../../weavers/gtdb_weaver/src/gtdb_weaver/factory.py).
[Spec](gtdb.spec.md), [plan](gtdb.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.
