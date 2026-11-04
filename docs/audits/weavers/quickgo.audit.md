# QuickGO weaver audit

Date 2026-10-08; source `d5e7543`; version `0.1.8`, core floor `0.13.0`.
Status audited locally; proposals only.

| ID | Priority/confidence | Finding/evidence | Recommendation |
|---|---|---|---|
| WV-QUICKGO-001 | P1 verified | Singleton path does not validate echoed geneProductId; injected P69905 annotation returned as P04637 result | Apply one correlation invariant to both single/bulk requests |
| WV-QUICKGO-002 | P1 verified | max_pages/source URL affect completeness but static fingerprint stays identical | Include semantic configuration in identity or declared effective parameters |
| WV-QUICKGO-003 | P1 verified | Invalid JSON raises out of fetch; row and pagination shape not fully validated | Source-local validation with per-query ERROR for expected data failures |
| WV-QUICKGO-004 | P2 researched proposal | No evidence, qualifier, aspect or taxon query filters | Add narrowly scoped declared filters with default behavior unchanged; preserve raw annotations |
| WV-QUICKGO-005 | P2 researched proposal | Term details lack parents/ancestors/replacement relations; reverse term→gene product workflow absent | Prioritize ontology relation detail; separately scope reverse search |
| WV-QUICKGO-006 | P2 verified | Builder/lifecycle and stale force instructions repeat shared gaps; README installation heading split as `In##` / `stallation` | Apply shared config/lifecycle policy and safe docs; repair heading |

## Research and capability comparison

Accessed 2026-10-08: [QuickGO API](https://www.ebi.ac.uk/QuickGO/api/),
[provider tutorial, 2009](https://pmc.ncbi.nlm.nih.gov/articles/PMC2794795/),
[GO annotation semantics](https://www.geneontology.org/docs/go-annotations/),
[GO enrichment guide](https://www.geneontology.org/docs/go-enrichment-analysis/).
Provider documentation establishes filtering and ontology/annotation uses; the GO
guide establishes scientific interpretation. These are not usage-frequency estimates.

| Workflow | Support | Gap |
|---|---|---|
| Retrieve protein annotations with supporting evidence | Good: raw rows, qualifiers/references and coverage retained | Response correlation/schema and budget identity need fixing |
| Select experimentally supported/non-negated/aspect-specific annotations | Partial: caller can inspect raw rows afterward | No declared backend filters; do not treat unfiltered inventory as positive evidence |
| Explore GO ontology hierarchy and obsolete terms | Partial: names/definitions/is_obsolete | Parent/ancestor/replacement relation detail absent |
| Prepare annotations for enrichment of a gene set | Partial retrieval only | No background/statistical analysis; defer enrichment engine, document correct external use |

Current: `list_go_terms` accession→distinct term fan set, aspects, term records,
raw annotations and coverage, max batch10; `describe_go_term` GO ID→name/aspect/
definition/detail, max batch10. API-only; no parameters/local build.

## Complete checklist assessment

- **Scientific correctness:** retained evidence/NOT qualifiers and explicit incomplete
  coverage are strengths. The term inventory is documented as unfiltered; do not
  relabel it a positive functional assertion or silently change default filtering.
  Source counts refer to query pagination, not immutable scientific snapshots.
- **Architecture:** shared dispatch + pure `_aggregate`/`_describe` already suitable.
  Separate a source-local page collector from annotation correlation/coverage projection
  using pure functions and a small explicit coverage value if helpful. Avoid generic
  pagination inheritance: QuickGO's source-count semantics are specialized.
- **Backend:** multi-accession queries with scaled page budget and per-accession cap;
  missing bulk echoes become ERROR; empty unseen incomplete results do not claim absence.
  Single path lacks same identity check. Term batching is supported; multi-chunk detail
  catches across all chunks, like PDBe direct-call limitation. Pacing present, no retry
  policy/client close; configuration private and ignored by public builder.
- **Data build/parity:** no DB/downloader/local backend. Fixture is testing support,
  not an alternative scientific source. Release metadata absent from exported rows.
- **Connectivity/usability:** good list/describe fan pair and registered keys. Bulk
  response budget can make partial results depend on other batch members; warnings
  must remain visible and cached partial results must not masquerade as larger-budget
  results. Declare knobs before advertising them through CLI/browser.
- **Docs/tests:** coverage/evidence examples and warning export tests already present.
  Retain them. Correlation parity, malformed pages, source-budget cache and explicit
  filter semantics missing. Shared stale force advice owner WV-EXAMPLE-001; lifecycle
  owner WV-UNIPROT-006. README heading is visibly malformed.
- **Licensing:** source CC-BY-4.0/citation/attribution, code MIT distinguished.

## Evidence and limits

**39 passed, 4 skipped**, strict fixture gate passed. Invalid JSON raised
JSONDecodeError; max_pages1/10 fingerprints equal. Singleton mock with P69905 echo
returned found=True with GO:0000001 for requested P04637. Live small GET term
GO:0006915 returned200 with one term. Full annotation/live suite not repeated.
Source/API/config/spec/fixtures and all API/live tests inspected; source unchanged.

[Backend](../../../weavers/quickgo_weaver/src/quickgo_weaver/backends/api.py),
[tests](../../../weavers/quickgo_weaver/tests/test_api.py),
[spec](../../../weavers/quickgo_weaver/weaver.spec.toml),
[docs](../../../weavers/quickgo_weaver/README.md).
[Proposed spec](quickgo.spec.md), [plan](quickgo.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.
