# PDBe weaver audit

Date 2026-10-08; revision `d5e7543`; version `0.1.8`, core floor `0.13.0`.
Status: audited locally, proposals not implemented.

## Findings

| ID | Priority/confidence | Finding and evidence | Proposed action |
|---|---|---|---|
| WV-PDBE-001 | P1 verified | `fingerprint()` ignores display limit and base_url; limits 1 and 25 have identical source identity despite different records/ids | Make result-affecting configuration explicit in query params or backend identity; validate positive limit |
| WV-PDBE-002 | P1 verified | Invalid JSON escapes as JSONDecodeError; unexpected object can become a false NO_MATCH | Validate source payload and convert expected decoding/schema failures into affected records' ERROR |
| WV-PDBE-003 | P2 verified | `_describe_structures` catches outside all chunks; later HTTP errors discard successes, and a not-found chunk exits before later work | Preserve per-chunk outcomes, continue unaffected chunks; test direct backend large batches |
| WV-PDBE-004 | P2 verified | Summary discards chain/entity mapping and coverage ranges; details lack quality, assembly, ligands and coordinate URLs | Prioritize mapping identity/ranges and structure quality as optional groups; scope assembly/ligand services separately |
| WV-PDBE-005 | P2 verified | Builder ignores config; owned client lacks closing; contributor force advice stale | Explicit configured composition/lifecycle; shared finding refs WV-UNIPROT-006 and WV-EXAMPLE-001 |
| WV-PDBE-006 | P2 verified | Spec claims no bulk endpoint, contradicting implemented POST batching; contributor expansion notes generic; docs promise same list without source-version qualification | Update source contracts and examples; document ranking limits and mutable source data |
| WV-PDBE-007 | P2 supported inference | Equal-coverage/resolution chains retain first response row, losing chain identity and method conflict evidence | Define deterministic chain-level tie handling when richer mapping records are added |

003 affects direct backend calls spanning >200 IDs; declared capability batch size 25
means the normal executor does not currently reach that multi-chunk description path.
It is not represented as an observed normal-executor failure.

## Research and workflow coverage

Primary sources accessed 2026-10-08:
[PDBe API services](https://www.ebi.ac.uk/pdbe/pdbe-rest-api),
[provider service catalogue](https://www.ebi.ac.uk/pdbe/pdbe-services),
[model-quality training](https://www.ebi.ac.uk/training/online/courses/exploring-pdb-entry/pdb-entry-overview/model-quality/),
[aggregated API paper, 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8570819/).
Provider tutorials and paper examples support these workflows; frequency ranking
is unmeasured. Do not equate coverage/resolution ranking with complete validation.

| Workflow | Current support | Gap/recommendation |
|---|---|---|
| Find experimental structures covering a UniProt protein | Good: bulk best_structures, distinct IDs, coverage/resolution ordering | Retain chain/entity and sequence mapping coordinates for interpreting coverage |
| Assess structure suitability/quality before analysis | Partial: method/resolution list metadata; title/dates summary | Optional validation/resolution detail; distinguish model quality from resolution |
| Map functional residues to structures using SIFTS | Partial entry-level relationship only | Residue mapping capability/groups need explicit chain/entity identity |
| Inspect ligands or biological assemblies for structural biology/drug research | Absent | Supported upstream; optional future expansion, not automatic scope |

## Capabilities and checklist

| Capability | Inputs/backend | Outputs and behavior |
|---|---|---|
| list_structures | accession/API | full distinct `pdb.id` fan set, top-N display IDs/records, true distinct count; summary/full groups |
| describe_structure | pdb.id/API | title, first method, dates, author/detail object; one detail group |

- **Correctness:** good input correlation, dedup/order/cap distinction and unknown-ID
  handling. Structure quality, biological assembly and mapped-chain coverage are not
  supplied; details should not imply they are. Null values become omitted strands.
- **Architecture:** thin shared dispatch is appropriate. Pure `_extract`, `_rank`,
  `_sort_key`, `_describe` already form a functional core. Keep source-local parsing;
  a helper for repeated chunk-response correlation is simpler than another backend
  inheritance layer. Extend detail via composed endpoint adapters only as services grow.
- **Backend:** bulk POST for lists/descriptions, one GET for single distinct accession;
  pacing supported. No source retries or Retry-After handling. Description-wide failure
  boundary differs from list per-chunk boundary. IDs are matched case-insensitively.
- **Build/local parity:** API-only; no external data build, DB replacement or local
  backend to audit. Zero-config discovery and source licensing metadata are present.
- **Configuration/cache:** private display limit unvalidated (negative accepted),
  fingerprint static, builder drops parameters; client ownership unresolved.
- **Connectivity/usability:** full set output plus describe consumer is a strong
  example; CLI list/fan/drill examples exist. Human-facing display limit cannot be
  selected through declared parameters. Python README only constructs a weaver.
- **Tests/docs:** read API, conformance/contract and five live tests; offline tests
  prove batching and wrong-accession isolation. Missing malformed schema, limit-cache
  and multi-chunk failures. Stale force advice shares Example's owner finding.

## Evidence

Package Make tests: **37 passed, 5 skipped**; strict fixture verification passed.
Scratch probes: invalid payload raised JSONDecodeError; `{"unexpected":"schema"}`
returned miss; limits 1/25 fingerprint equal; negative limit accepted.
Small live GET `/pdbe/api/pdb/entry/summary/1tup` returned 200 keyed by 1tup.
No full live suite, POST replay or quality/ligand endpoint certification performed.
Baseline log `.audit-local/weaver-audit-pdbe-baseline.log`.

Evidence: [backend](../../../weavers/pdbe_weaver/src/pdbe_weaver/backends/api.py),
[spec](../../../weavers/pdbe_weaver/weaver.spec.toml),
[tests](../../../weavers/pdbe_weaver/tests/test_api.py),
[factory](../../../weavers/pdbe_weaver/src/pdbe_weaver/factory.py),
[docs](../../../weavers/pdbe_weaver/README.md).
See [spec](pdbe.spec.md) and [plan](pdbe.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.
