# NCBI weaver audit

Date 2026-10-08; revision `d5e7543`; package `0.2.4`, core floor `0.13.3`.
Status audited locally; proposals only. Preserve the custom taxonomy runtime decision
in [A08](../../refactoring/ncbi-dispatch-assessment.md).

## Findings

| ID | Priority/confidence | Evidence and implication | Action |
|---|---|---|---|
| WV-NCBI-001 | P1 reproduced | Direct database builder clears and commits existing reference tables before parsing; malformed nodes erase 12 fixture taxa. CLI uses this direct builder | Stage, validate and atomically publish every public build path; preserve old target on any failure |
| WV-NCBI-002 | P1 reproduced | A valid CLI build ends with AttributeError accessing removed `lineage_cache_count`; current CLI tests cover download helper only | Render current summary fields and exercise actual CLI run/report/exit |
| WV-NCBI-003 | P1 reproduced | Products/sequence gather drops exceptions; requested products with 503 becomes OK, no strands/warnings, products group marked computed | Represent requested enrichment failure explicitly; do not claim/cache completed group |
| WV-NCBI-004 | P1 reproduced/code | Gene symbol correlation uses first echoed result via setdefault; ambiguous fixture selects first source gene. Fuzzy candidate ordering follows source order | Explicit deterministic ambiguity/representative policy, review where identity is uncertain |
| WV-NCBI-005 | P1 code | Taxonomy resolve does not catch HTTP errors; malformed JSON/shapes escape multiple operations | Endpoint-aware source boundary returning per-query ERROR/NO_MATCH; preserve cancellation |
| WV-NCBI-006 | P2 verified/code | API fingerprint ignores fuzzy policy/endpoint; owned client lacks close; api_key alone silently discarded by introspection branch | Explicit configured construction, lifecycle and semantic identity; reference WV-UNIPROT-006 |
| WV-NCBI-007 | P2 code | Children/genomes/orthologs and fuzzy misses run serial per-query; bulk summaries already implemented | Bulk where supported, bounded concurrent single-ID pagination with pacing and duplicate reuse |
| WV-NCBI-008 | P2 code | Repeated pagination tokens can loop; gene products only first page then cap200; sequence records cap200 without coverage | Source-local bounded page collector; honest totals/coverage and detail caps |
| WV-NCBI-009 | P2 verified | Public TaxonMatch/CandidateMatch/LineageEntry lack JSON round trips; monolithic interface supplies six unsupported defaults, implementations structurally typed | Explicit boundary serialization; small source-local operation protocols/composed adapters only where useful |
| WV-NCBI-010 | P2 verified/inference | Docs describe adding every output through TaxonMatch though six capabilities use LookupRecord; resolver version queries obsolete taxonbridge; local child queries and merged/deleted taxid handling absent | Correct extension/build docs and source version reporting; assess targeted taxonomy additions |

003 also applies to requested genome sequences by the same inspected pattern; only
products failure was reproduced. 004 proves order-dependent selection, not frequency
of ambiguous live NCBI symbols. 008 reports code behavior, not observed live truncation.
001 concerns public direct build/CLI; consent-gated `ensure_taxonomy_db` already builds
into a temporary target and safely publishes. Do not undo that existing protection.

## Source research and workflow matrix

Primary sources accessed 2026-10-08:
[ortholog tutorial](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/tutorials/download-ortholog-dataset/),
[genome retrieval](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/how-tos/genomes/download-genome/),
[gene metadata](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/how-tos/genes/get-gene-metadata/),
[Taxonomy FAQ](https://www.ncbi.nlm.nih.gov/books/NBK54428/?report=classic).
Tutorials were read; FAQ/gene metadata supported by indexed primary-source text.
FTP readme retrieval failed. These support workflow relevance, not popularity counts.

| Workflow | Current coverage | Gap/decision |
|---|---|---|
| Normalize organism names, inspect alternatives and lineage | Strong local resolver; API exact/fuzzy and lineage | Preserve review richness, normalize API failure/order |
| Select reference/annotated assemblies and inspect chromosome metadata | API list/describe, declared filters and full accession fan set | Requested sequence failure/coverage must be honest |
| Map symbols to stable Gene IDs | Taxon parameter defaults human; first matching gene chosen | Symbols can be nonunique; avoid unexplained high-confidence selection |
| Inspect genes, transcripts/proteins and orthologs across taxa | Summary/products and ortholog fan | Product pagination/failure; metadata retrieval is not sequence-file download |
| Resolve historical merged/deleted taxonomy IDs | No merged/deleted tables ingested | Conditional status/redirect behavior, real dump samples and release-aware provenance |
| Offline lineage and descendant exploration | Lineage supported; descendants API-only | Conditional local descendant query using existing parent structure |

Large sequence dataset acquisition, CLI wrappers around every NCBI service and
scientific orthology inference are not required for this metadata weaver.

## Full checklist

- **Capabilities/connectivity:** eight operations; taxonomy name/ID support local/API,
  six gene/genome operations API-only. Registered organism, gene and genome bridges;
  list children/genomes/orthologs produce full distinct sorted ID sets with capped
  display records and total counts. Species/rank/default filters are explicit.
- **Architecture/OOP:** source-local custom dispatch remains justified by taxonomy
  review candidate/warning fidelity. Six capabilities already reuse core lookup
  mapping. Separate source HTTP adapters for taxonomy/gene/genome only if they reduce
  maintenance coupling; no core biological hierarchy or artificial universal template.
  Small operation protocols fit actual structural implementations better than widening
  an ABC with unsupported methods. Shared HTTP validation/collection can be composition.
- **Functional design:** pure normalizers/selection should accept validated source
  data, return explicit coverage and avoid hidden first-hit policy. Keep IO, page
  collection and mapping separate; no need to rewrite owned resolver service/repositories.
- **Build/data:** safe consent/lock/headroom/hash/atomic setup exists. Direct public
  rebuild and CLI bypass safety; source archive hash/build version already valuable.
  Never download full taxonomy for an audit; all destructive reproduction used temp files.
- **Batch/order/errors:** chunked taxonomy POST and gene/genome summary GET already
  respect bulk endpoints. Secondary requests gathered concurrently. Remaining serial
  endpoints and broad group failure need bounded per-input treatment; direct dispatch
  length/unknown-param differences were documented in A08, not newly caused defects.
- **Groups/parameters/cache:** requested groups gate secondary IO; taxonomy direct
  params currently ignored, lookup params validated. Group-completion errors and fuzzy
  source identity matter before cache/resume expansion; no cache implementation here.
- **Documentation/usability:** useful CLI and Python constructor examples, consent and
  backend selection documented; actual build CLI failure and outdated contributor
  extension/version language need correction. Handwritten vocab must stay handwritten.
- **Tests/releases:** all three version sites/floor reviewed; 126 passed, 11 skipped,
  strict fixture verification passed. No full live NCBI suite run in this audit.
  Strong taxonomy/bulk/review/fan coverage, gaps in CLI execution, failed rebuild,
  requested enrichment errors, pagination cycles and ambiguous symbols.

## Reproduction and source evidence

Run `.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_ncbi_build.py`.
It confines writes to temporary files: existing taxa12→0 after ValueError, and a valid
CLI build raises missing lineage_cache_count. Earlier MockTransport probes reproduced
products 503→OK/computed products and first-hit gene selection without network access.

[API backend](../../../weavers/ncbi_weaver/src/ncbi_weaver/backends/datasets_v2.py),
[builder](../../../weavers/ncbi_weaver/src/taxonomy_resolver/build.py),
[CLI](../../../weavers/ncbi_weaver/src/taxonomy_tools/build_ncbi_taxonomy.py),
[factory](../../../weavers/ncbi_weaver/src/ncbi_weaver/factory.py),
[intermediate](../../../weavers/ncbi_weaver/src/ncbi_weaver/intermediate.py).
[Proposed spec](ncbi.spec.md), [plan](ncbi.plan.md).
