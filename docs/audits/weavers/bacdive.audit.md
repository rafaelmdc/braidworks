# BacDive weaver audit

Date: 2026-10-08; source revision `d5e7543`; package 0.1.6, core floor 0.13.0.
Status audited locally; no production changes.

## Findings

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-BACDIVE-001 | P1 reproduced/code | Genus-only input selects first species type strain; subspecies/qualifiers discarded; chosen BacDive ID and matched taxonomy not emitted | Validate identity granularity, expose exact representative identity and explicit selection scope |
| WV-BACDIVE-002 | P1 reproduced/code | Scan exhaustion returns same NO_MATCH as complete absence; cap1000 default builder vs200 configured builder; cap/source omitted from fingerprint | Report coverage/budget exhaustion, consistent defaults and semantic source identity |
| WV-BACDIVE-003 | P1 reproduced | Taxon404 becomes ERROR; invalid JSON escapes; IDs/record shapes unvalidated | Endpoint-aware source validation/status values; missing traits remain legitimate sparse data |
| WV-BACDIVE-004 | P2 reproduced/code | Serial per-name loop repeats duplicate queries; only each taxon's strain fetch is bulk | Reuse distinct name scans, bounded concurrent taxonomy chains and merged/chunked detail requests where feasible |
| WV-BACDIVE-005 | P2 code | First type strain/first subfield/optimum record selected in source order; conflicting measurements/references/units lost | Stable ID selection, raw evidence/measurement context and explicit conflict policy |
| WV-BACDIVE-006 | P2 verified | README says BacDive describes type strains, misplaces motility/spore groups; no exact strain capability or culture collection/genome mapping | Correct scope/groups and prioritize list_strains→describe_strain plus identifiers/culture evidence |
| WV-BACDIVE-007 | P2 verified/code | Builder ignores config; owned client unclosed; stale force-regeneration docs, stale scan default/multi-ID uncertainty | Reference WV-UNIPROT-006 and WV-EXAMPLE-001; accurate configuration examples |

001 fixture shows genus accepted and chosen trait, not a live genus result. 002 could
hide a type strain beyond the cap; no claim all capped searches have such a strain.
005 is an evidence-preservation improvement, not a requirement to compute species means.

## Research/workflow coverage

Primary sources accessed2026-10-08:
[official API](https://api.bacdive.dsmz.de/),
[advanced search](https://bacdive.dsmz.de/help/advanced_search.htm),
[isolation search](https://bacdive.dsmz.de/help/isolation-source-search.htm),
[strain field documentation](https://www.api.bacdive.dsmz.de/strain_fields_information),
[genomic feature search](https://bacdive.dsmz.de/genesearch).
API explicitly documents keyless access since February2026, multi-ID detail limit100,
and genus/species/subspecies paths. Indexed field documentation uses internal search
field names; do not substitute those names for observed detail JSON without probing.

| Provider-supported workflow | Current coverage | Gap/proposal |
|---|---|---|
| Compare phenotype of specific cultured strains | Seven traits from one selected type strain | Exact BacDive ID/culture collection lookup; strain list/describe and provenance |
| Choose cultivation conditions/media | Temperature/pH optimum as strings | Units/ranges/media/measurement evidence, avoid first-optimum overgeneralization |
| Explore habitat/isolation context | Absent | Conditional isolation source group and controlled labels |
| Connect cultured strains to genome/16S accessions | Absent | Conditional registered sequence/genome bridges from observed records |
| Advanced phenotype/cohort/genomic feature search | Absent | Separate query service proposal; do not overload exact entity description |

Type-strain selection is a nomenclatural representative policy, not proof a phenotype
is typical of every isolate. Provider includes non-type strains. Existing narrow capability
can remain if its selected-strain identity and scope are honest. No popularity counts.

## Complete checklist

- **Capabilities:** one API max50 lookup, scientific-name input; morphology4,
  physiology1 and growth2 outputs. No params/fan identifiers. Terminal trait enrichment
  is useful behind NCBI/UniProt but exact strain IDs would support drill-down.
- **Architecture/OOP:** current shared dispatch plus backend composition is sufficient.
  Extract source-local paginated strain discovery and pure representative/trait projection;
  an explicit strategy only if adding multiple accepted selection policies. No repository
  layer, subclass per trait or universal resolver template needed.
- **Functional design:** existing dict/list helpers and trait projection are useful pure
  seams; add validated identity/measurement normalization, preserve conflicting evidence.
  No public dataclasses currently needing additional JSON round trips.
- **Backend/batching/errors:** strain IDs fetched100 per request; taxon chains paginate
  serially. Duplicate names and scan budget semantics need improvement; empty repeated
  next-page loops lack cycle protection. Network errors become per-record values, JSON
  does not. Pacing wrapper exists; preserve it under concurrency.
- **Build/parity/provenance:** no local data build/backend; deterministic MockTransport
  fixture only. Static API contract does not pin live strain data release. Record missing
  field is not false/negative phenotype. Optional bulk snapshots need separate scope.
- **Groups/parameters/cache:** whole selected record fetched and pure mapper slices
  groups; no evidence of requested-output bug here. Scan policy should be declared/identified
  consistently and incomplete scan not cached as definitive absence.
- **Docs/usability:** CLI examples and construction present; Python execution/config
  example missing. Contributor known-limitations section honestly acknowledges strain scope
  but README conflicts; documented default200 differs from production1000.
- **Tests/releases:** 29 passed,2 skipped; strict fixture gate passed. Existing batch
  test validates IDs for one name, not batched names. Add 404/malformed, cap coverage,
  duplicate/concurrent queries, genus/subspecies identity and shuffled strain evidence.

Evidence: `.audit-local/bacdive-audit-probe.py` produced genus trait success, four
requests for two identical inputs, budget fingerprint collision, 404 ERROR and malformed
JSONDecodeError. No new live BacDive suite run.
[API](../../../weavers/bacdive_weaver/src/bacdive_weaver/backends/api.py),
[factory](../../../weavers/bacdive_weaver/src/bacdive_weaver/factory.py),
[spec](../../../weavers/bacdive_weaver/weaver.spec.toml).
[Proposed spec](bacdive.spec.md), [plan](bacdive.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.

[Retained offline reproduction](../reproductions/weaver_bacdive.py) runs without network;
all database writes stay in temporary directories.
