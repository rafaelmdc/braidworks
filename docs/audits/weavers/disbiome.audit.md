# Disbiome weaver audit

Date: 2026-10-08; revision `d5e7543`; package 0.3.2/core floor 0.13.3.
Status audited locally; proposals only.

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-DISBIOME-001 | P1 reproduced/verified | Manifest/backend consumes species_id exclusively although source includes genus associations; fixture Enterococcus1350 only works when mislabeled species_id. README/CLI uses generic id and gets miss | Explicit rank-aware input policy preserving exact taxid lookup and optional ancestor roll-up, never imply genus effect measured for each species |
| WV-DISBIOME-002 | P2 verified/code | Summary/compact lookup loads/parses all full_json and builds all views; spec claims light slice never pays blob cost | Output-group SQL/projection gating or truthful cost documentation; measure before changing schema |
| WV-DISBIOME-003 | P2 verified | Compact associations omit experiment/publication identity and quality context; disease IDs only buried, no reverse disease→microbe join | Evidence IDs on compact records; conditional disease bridge/list/describe or reverse capability |
| WV-DISBIOME-004 | P2 code | Build joins silently allow missing foreign rows, duplicate experiment IDs unconstrained and shape unvalidated; sequential table fetches not a frozen snapshot | Build validation/coverage/provenance manifest; preserved source records and snapshot limits |
| WV-DISBIOME-005 | P2 verified/code | Progress argument ignored, docs incorrectly promise TTY prompting; kwargs ignored and unsafe regeneration instructions | Explicit setup/configuration/progress and accurate CLI/Python examples; shared owner references |
| WV-DISBIOME-006 | P3 supported inference | Batch repeats per-query SQL/JSON; source rank/body-site/method/outcome filters not declared | Deduplicate/multi-key SQL if measured; optional declared evidence filters with default preservation |

1591 is currently NCBI species Lactobacillus sp., not genus1578; primary taxonomy
verification prevented using the stale source label as a genus example. Enterococcus1350
fixture is a genus. Production prevalence of lost genus rows not measured by a full build.

## Research and workflow coverage

Primary sources accessed2026-10-08:
[provider help](https://disbiome.ugent.be/help),
[export endpoints](https://disbiome.ugent.be/export),
[original database paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5987391/),
[NCBI1591](https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=1591).
Indexed provider/paper text demonstrates searching by disease, organism/method and
reviewing experiment/control/publication context; no popularity claims.

| Workflow | Current coverage | Gap/decision |
|---|---|---|
| Review microbe abundance changes associated with disease | Exact taxid indexed experiment rows | Correct genus/species reachability and preserve measured rank |
| Examine conflicting outcomes across studies/body sites/methods | Raw per-experiment directions and full joined publication retained | Compact evidence IDs/quality context and optional filters |
| Start from disease and find reported organisms | Bulk iterator available, no reverse routable capability | Conditional MedDRA disease→taxon fan and disease detail bridge |
| Inspect quantitative results/quality | Full source fields retained | Typed evidence projection, no automatic effect-size pooling across incompatible measures |

Associations are study observations, not causation or diagnosis. Count already counts
experiment records, not unique diseases; preserve/document that distinction.

## Complete checklist

- **Capabilities/connectivity:** one local list_diseases; species_id input, three
  groups; disease-name list is leaf, no fan ID. NCBI species lifting helps strain→species
  but excludes useful generic/genus entry; do not fix via unsafe universal inheritance.
- **Architecture/OOP:** shared dispatch, SourceBinding and single threaded batch read
  session are good. Source-local pure join/projection plus focused query helper suffice;
  repository abstraction only if different storage/service implementations justify it.
- **Functional:** existing cleaning/content-hash/join functions useful; validate source
  IDs, dangling joins and duplicate experiment semantics explicitly. No public dataclass.
- **Build/provenance/parity:** consent/lock/headroom/atomic setup with source hash and
  build_id implemented. Whole tables small; no runtime API parity required. Validator
  checks hash/nonempty only, not join/schema coherence. Publication metadata retained in
  full view; document acquisition timestamp and sequential snapshot limitations.
- **Batch/errors/cache:** order preserved off event loop, read session pinned; malformed
  stored JSON/schema can raise. Group claims complete available records but filters/gating
  need honest semantics. No evidence of true-count cap bug; full records uncapped.
- **Docs/usability:** README input/CLI conflicts with spec and prompt claim with setup;
  contributor rank note already acknowledges genus data, but doesn't repair reachability.
  Real query + setup guidance present; Python actual execution example missing.
- **Tests/releases:** 28 passed,1 skipped and strict passed; fixture/contract label genus
  inputs as species, hiding rank inconsistency. Add generic/genus/strain routed examples,
  build invalid/duplicate/dangling cases and compact evidence. No live acquisition run.

Evidence `.audit-local/gut-weavers-probe.py`: genus1350 generic key→NO_MATCH, mislabeled
species key→OK. [Backend](../../../weavers/disbiome_weaver/src/disbiome_weaver/backends/local.py),
[setup](../../../weavers/disbiome_weaver/src/disbiome_weaver/setup.py),
[spec](../../../weavers/disbiome_weaver/weaver.spec.toml),
[fixture](../../../weavers/disbiome_weaver/src/disbiome_weaver/fixture.py).
[Proposed spec](disbiome.spec.md), [plan](disbiome.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.

[Retained offline reproduction](../reproductions/weaver_gut_sources.py) runs without network;
all database writes stay in temporary directories.
