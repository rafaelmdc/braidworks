# MONDO weaver audit

Date: 2026-10-08; revision `d5e7543`; package 0.2.2/core floor 0.13.3.
Status audited locally; proposed changes only.

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-MONDO-001 | P1 reproduced | Shared name/xref matches choose LIMIT1 ordered only by priority/equivalence; reversed equal-priority input reverses chosen MONDO identity | Preserve candidates/mapping relation and explicit deterministic reviewed selection |
| WV-MONDO-002 | P1 verified/code | Non-equivalent xref accepted as confident identity; mapping precision reduced to bool and not emitted | Distinguish exact/broad/narrow/related alignment and policy, never imply every xref is equivalence |
| WV-MONDO-003 | P1 reproduced/code | Recursive UNION includes changing depth; cyclic isa never deduplicates visits, build validation permits cycle | Validate DAG before publication and bound/path-guard traversal; no indefinite lookup |
| WV-MONDO-004 | P2 verified | No describe by produced disease.mondo.id; obsolete/replaced/consider IDs discarded, definitions/external mappings absent | Conditional direct-ID describe and obsoletion/mapping metadata |
| WV-MONDO-005 | P2 code | Both ancestor queries always executed even term/ID-only; depth repeats traversal and SQL per ancestor | Source-local group-gated graph query, one traversal reused; measured batch dedup |
| WV-MONDO-006 | P2 reproduced/code | Missing version stored unknown yet DB accepted; original OBO hash/acquisition metadata absent; validator lacks DAG/edge coherence | Validated source descriptor/hash, pinned release and complete graph checks |
| WV-MONDO-007 | P2 verified/code | Config kwargs ignored, stale contributor regeneration and source comments; hardcoded coverage percentages lack reproducible audit evidence | Shared explicit-config/safe-doc owners and executable capability/output examples |

001/003/006 reproduce on tiny temporary OBO-derived databases. Cycle probe uses SQLite
progress handler to interrupt safely, not a hung worker. 002 fixture demonstrates use of
non-equivalent xref; real mapping relation diversity supported by provider docs. Hash issue
is provenance fidelity, not a claim source-binding build_id misses current rebuilt DB.

## Research and workflows

Primary sources accessed2026-10-08:
[mapping precision](https://mondo.readthedocs.io/en/latest/editors-guide/mappings/),
[FAQ](https://mondo.monarchinitiative.org/pages/faq/),
[documented users](https://mondo.monarchinitiative.org/pages/users/),
[downloads](https://mondo.monarchinitiative.org/pages/download/),
[curator obsoletion discussion](https://github.com/monarch-initiative/mondo/discussions/2765).
Indexed official texts explain curated alignment precision, harmonization use and
replacement handling. User list supplies actual adoption examples, no popularity ranking.

| Workflow | Current coverage | Gap/decision |
|---|---|---|
| Harmonize disease IDs from different terminology | MeSH/MedDRA→one MONDO | Mapping relation/candidates and ambiguity, exact vs related semantics |
| Search disease name/exact synonym | Normalized exact label/synonym index | Duplicate exact names need review/stability; no fuzzy promise |
| Browse parent/ancestor disease classes | Direct parents, ancestors including self, shortest root depth | DAG safety, group-gated query; depth is topology not validated similarity score |
| Describe known MONDO term, follow obsolete identifiers | Cannot consume own ID; obsolete terms discarded | Conditional describe_disease with definitions/status/replacements/source mappings |
| Integrate rare disease/gene/phenotype datasets | Disease identity/hierarchy substrate | Additional external ID bridges as reviewed scope; no diagnosis/modeling inference |

## Complete checklist

- **Capabilities/connectivity:** three local lookup entry capabilities, MeSH/MedDRA/name,
  term and ancestors groups. Existing generic lookup verb differs from preferred resolve/
  describe naming; rename only with deliberate compatibility policy. Produced MONDO key
  not directly consumed here. Ancestor list is leaf records, no unsupported fan claim.
- **Architecture/OOP:** shared dispatch/SourceBinding/thread-owned read sessions fit.
  Focused ontology graph query service and pure parser/mapping selection composed locally
  are enough; no class per terminology or universal ontology framework in core.
- **Functional:** normalization/parser already pure seams; preserve precise alignment
  and obsolete metadata in validated representation. `_Term` private mutable parse state
  is reasonable; public boundary candidates use core JSON contracts.
- **Build/provenance:** safe consent/lock/headroom/temp publication present; OBO streamed
  into list of terms then indices. Obsolete removed and missing parents silently filtered;
  full DAG/source validation missing. SourceBinding protects generations; release descriptor
  should add observed hash and unambiguous version instead of treating unknown as release.
- **Batch/errors/groups:** threaded order preserved; SQL per query, ancestors traversed
  twice, graph cycle can hang despite UNION. Unknown IDs legitimate miss; structural bad
  ontology should fail validation with actionable source error, not look like root depth0.
- **Docs/usability:** current setup/name-entry overview good; no output/capability table or
  real Python execution. Explain multiple ancestors, self inclusion and mapping precision.
  Spec coverage claims14%/60% historical estimate not independently verified here.
- **Tests/releases:** 39 passed,1 skipped/strict passed. Good synonyms/parents/ancestors
  fixture coverage; no equal-priority shuffled mapping, relation types, cycles/obsolete terms,
  missing version or group-query-count checks. Retain conformance unchanged.

`.audit-local/mondo-audit-probe.py` verifies reversed identity selection, accepted missing
release and cyclic query interrupted by guard. No new live OBO download/build.
[Backend](../../../weavers/mondo_weaver/src/mondo_weaver/backends/local.py),
[setup](../../../weavers/mondo_weaver/src/mondo_weaver/setup.py),
[spec](../../../weavers/mondo_weaver/weaver.spec.toml).
[Proposed spec](mondo.spec.md), [plan](mondo.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.

[Retained offline reproduction](../reproductions/weaver_mondo.py) runs without network;
all database writes stay in temporary directories.
