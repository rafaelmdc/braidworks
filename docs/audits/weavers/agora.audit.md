# AGORA weaver audit

Date: 2026-10-08; source revision `d5e7543`; package 0.2.2, core floor 0.13.3.
Status audited locally; proposals only.

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-AGORA-001 | P1 reproduced | Requested missing reaction DB or uncached/nonconsented SBML returns OK with no strands/warnings and computed reactions/model group | Explicit unavailable/partial coverage; never cache uncomputed group |
| WV-AGORA-002 | P1 code | Individual model cache accepts any nonempty file; direct download has no lock/staged validation; model artifacts/cache directory/availability absent from fingerprint | Validated atomic model artifact service, release/content identity and honest portable model references |
| WV-AGORA-003 | P2 code | Malformed SBML models skipped with log only; populated DB validates globally, missing model repertoire becomes empty list with no coverage | Build manifest of processed/skipped models, completeness contract and per-model availability |
| WV-AGORA-004 | P2 verified | Reaction and genome identifiers buried in leaf records; no model-ID drill-down/fan bridge; README calls reaction output intermediate despite no routable key | Conditional list_reconstructions/describe_reconstruction pair and explicit genome/reaction crossrefs |
| WV-AGORA-005 | P2 code | Direct reaction builder upserts old data, live VMH annotation metadata not fully recorded; XML only clears reaction elements, archive path failure cleanup incomplete | Reference direct-replacement owner WV-GTDB-005; measured streaming/provenance and cleanup |
| WV-AGORA-006 | P2 verified/code | Config kwargs ignored, configured wrapper forces auto_setup and duplicates explicitly supplied auto_setup; docs omit model group and stale regeneration | Explicit construction/consent, safe extension and model usage docs |
| WV-AGORA-008 | P2 verified | Strict verification warns CC-BY-NC-4.0 is unrecognized and conservatively restricted | Retain restriction; review known-restricted identifier/attribution rendering without relabeling source as permissive |
| WV-AGORA-007 | P3 code | Cached bundled crosswalk returns mutable shared lists/dicts; query reaction reads loop per model | Pure copied/immutable projection and measured bulk SQL if warranted |

001 reproduced via execute_batch on a known bundled taxid and empty temporary cache.
002 normal test deliberately accepts fake SBML; validity is not currently checked.
005 normal ensure setup already stages a new DB, so stale rows concern direct builder.
No claim reaction presence proves active metabolism or any clinical treatment result.

## Research and capability coverage

Primary sources accessed2026-10-08:
[provider repository](https://github.com/VirtualMetabolicHuman/AGORA2),
[original paper](https://pubmed.ncbi.nlm.nih.gov/36658342/),
[provider reconstruction catalogue](https://www.digitalmetabolictwin.org/reconstructions).
Paper abstract/indexed primary text demonstrates strain-resolved metabolic/drug-conversion
modeling; repository confirms downloads live externally. No popularity counts asserted.

| Workflow | Current support | Gap/decision |
|---|---|---|
| Find strain-resolved models from organism ID | Bundled7302 crosswalk; strain taxids map to lists | Expose model/genome identity and taxid granularity explicitly |
| Inspect reconstruction reaction repertoire | Optional local DB, ordered model/reaction records | Per-model build availability and annotation provenance |
| Load SBML into COBRA/community metabolism tooling | Optional individual model local paths | Validated content/reference/lifecycle, portable retrieval guidance |
| Model diet, exchange flux or drug biotransformation | Model retrieval substrate only | Solver/diet/objective/community assumptions belong to separate computation; optional reaction/metadata links |

One max50 local lookup capability consumes ncbi.taxon.id; core/reactions/model groups
are leaf lists. No declared parameters/set fan. All version sites inspected; source
release2.01, upstream data terms distinct from software MIT. Audit makes no new legal claim.

## Full checklist

- **Architecture/OOP:** shared runtime appropriate; SourceBinding plus threaded batch
  owns reaction read scope and prevents mixed DB generations. Keep it. Extract small
  composed model artifact acquisition/validation service rather than extending generic
  backend hierarchy; coverage belongs in source records/mapping contract.
- **Functional:** existing crosswalk sorting/reaction normalization useful; make
  parsing and build-summary coverage explicit. Avoid hidden mutation via cached lists.
  No public boundary dataclasses currently require additional serializers.
- **Build:** archive parsing per model, reaction membership DB and annotation join;
  generic consent/lock/headroom/atomic ensure present. Individual model path lacks same
  guarantees; distinguish fixed release model and live VMH reaction annotations. Source
  identity metadata build_id already prevents equal-hash rebuilt DB cache collision.
- **Batch/error/groups:** entire batch off event loop and input order preserved. Repeated
  model downloads/reaction reads serial inside worker; network errors can escape local
  fetch through artifact download. Missing requested resource cannot mean computed empty.
  Optional model acquisitions stay consent-gated; no archive downloaded for this audit.
- **Connectivity:** buried gcf_id/ec/kegg/rhea aren't planner outputs; add genuine bridge
  keys deliberately if accepted. Model detail should consume the emitted model ID.
- **Docs/usability:** Python constructors but no actual query/model execution example;
  README lists two groups while spec has three; contributor expansion TODO still present.
  Clarify species-vs-strain taxids and model presence vs biological capacity.
- **Tests:** 21 passed,1 skipped; strict passed. Model positive fixture accepts fake XML,
  negative test asserts silent OK omission; keep contract tests and deliberately review
  behavior-specific test updates for new coverage contract. Add failed/partial download,
  invalid model, missing requested resources, malformed model inventory and repeat builds.

Source: [backend](../../../weavers/agora_weaver/src/agora_weaver/backends/local.py),
[dataset](../../../weavers/agora_weaver/src/agora_weaver/dataset.py),
[setup](../../../weavers/agora_weaver/src/agora_weaver/setup.py),
[spec](../../../weavers/agora_weaver/weaver.spec.toml).
Strict passed with the existing unknown-license warning for CC-BY-NC-4.0; it remains conservatively restricted. No new live suite or full archive build. [Spec](agora.spec.md), [plan](agora.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.

[Retained offline reproduction](../reproductions/weaver_gut_sources.py) runs without network;
all database writes stay in temporary directories.
