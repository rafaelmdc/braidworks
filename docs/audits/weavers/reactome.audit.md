# Reactome weaver audit

Date 2026-10-08; revision `d5e7543`; package `0.1.8`, core floor `0.13.0`.
Status audited locally; proposals not implemented.

| ID | Priority/confidence | Finding/evidence | Recommendation |
|---|---|---|---|
| WV-REACTOME-001 | P1 verified | Display limit/source endpoint omitted from static fingerprint; negative limit accepted | Declared positive query limit or immutable semantic backend identity |
| WV-REACTOME-002 | P1 verified | Invalid JSON raises JSONDecodeError; non-list payload becomes miss | Validated source response boundary and affected-record ERROR |
| WV-REACTOME-003 | P2 verified | Detail endpoint/chunk failure catches outside loop, discards good chunks or skips later ones after not-found | Per-chunk outcomes; direct backend large-batch tests (normal batch25 < chunk100) |
| WV-REACTOME-004 | P2 researched proposal | Pathway details are title/species/disease flags only; hierarchy/participants/reactions/evidence absent | Add hierarchy and participant drill-down with stable IDs before broad analysis features |
| WV-REACTOME-005 | P2 verified | Config ignored, owned clients unclosed, generic stale contributor instructions | Shared config/lifecycle WV-UNIPROT-006 and safe docs WV-EXAMPLE-001 |
| WV-REACTOME-006 | P2 supported inference | Pathway listing does not retain species/inference/source release; dedup first wins on conflicting rows | Preserve relevant evidence and qualify membership/ordering semantics |

## Research/workflow comparison

Sources accessed2026-10-08: [pathway browser guide](https://reactome.org/userguide/pathway-browser),
[analysis guide](https://reactome.org/userguide/analysis),
[Content Service](https://reactome.org/dev/content-service),
[download/mapping catalogue](https://reactome.org/download/).
These demonstrate pathway lookup, hierarchy/participants and cohort analysis, not
quantitative usage frequency. Reactome's curated human pathways and computationally
predicted nonhuman pathways must not be presented as equivalent evidence.

| Workflow | Current support | Gap/action |
|---|---|---|
| Associate a protein with pathways | Good lookup, full distinct pathway fan set | Document endpoint's membership/hierarchy semantics and inference provenance |
| Explore pathway events, nested pathways and participants | Partial: name/species summary only | Hierarchy/participants/reaction consumers are useful connected extensions |
| Analyze a gene/protein dataset for enriched pathways | Absent; per-protein membership is not enrichment | Separate cohort-level analysis contract/background/statistics decision |
| Overlay expression or compare species | Absent | Distinct analysis services; defer until user workload chosen |

## Capability and design checklist

`list_pathways`: accession→full pathway IDs, top30 names/records and true distinct
count, summary/full groups; `describe_pathway`: stable pathwayID→name/species/disease/
detail, one detail group. Both API, maxbatch25, no declared params/local build.

- **Correctness:** complete identifier fan versus capped display and deterministic ID
  sorting are strengths. Listing membership is neither pathway activity nor enrichment.
  First method-like metadata projection is intentionally small; add richer evidence
  explicitly. Empty/malformed schema distinction and config identity need fixes.
- **OOP/functional:** existing template dispatch and injected strategy appropriate.
  `_extract`/`_describe` are pure. Keep chunk collection and projection separate with
  small helpers; a pathway service adapter earns its place only as hierarchy endpoints
  are added. Do not add generic analysis inheritance.
- **Transport:** list per-accession bounded concurrency4; describe bulk POST, input
  correlation by stId; paced client. Failures values for HTTP, source parsing unguarded.
  No explicit retry/lifecycle; detail failure boundary differs from per-query list.
- **Build/parity:** API-only; no scientific local DB lifecycle to invent. Source
  contract constant is not Reactome release provenance; capture release when feasible.
- **Connectivity/usability:** list/describe fan pair works; optional participants
  could bridge back to protein IDs if source mapping verified. Display cap available
  only in manually composed backend, public builder drops configuration. CLI examples
  and licensing/citation exist; Python only construction; expansion notes generic.
- **Tests:** lookup dedup/cap, bulk describe, status mapping and bounded order tested;
  malformed payload, config/cache identity and richer evidence cases absent. Read
  three live tests; no cohort-level analysis supported or tested.

## Evidence

**33 passed, 3 skipped**; strict fixture verification passed. Invalid JSON escaped;
limit1/30 fingerprints equal. Live GET mapping UniProt/P04637/pathways returned200
with46 rows. No full live suite/analysis run, no large downloads.
[Backend](../../../weavers/reactome_weaver/src/reactome_weaver/backends/api.py),
[factory](../../../weavers/reactome_weaver/src/reactome_weaver/factory.py),
[spec](../../../weavers/reactome_weaver/weaver.spec.toml),
[tests](../../../weavers/reactome_weaver/tests/test_api.py).
[Spec](reactome.spec.md), [plan](reactome.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.
