# FAPROTAX weaver audit

Date: 2026-10-08; revision `d5e7543`; package 0.1.1/core floor 0.1.8, bundled data 1.2.12.
Status audited locally; no implementation changes.

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-FAPROTAX-001 | P1 reproduced | Pattern genus→epithet compared to exact NCBI full lineage names: Methanosarcina + Methanosarcina barkeri yields no functions, artificial epithet-only lineage yields nine | Source-grammar-compatible ranked-name normalization and reference-oracle differential tests |
| WV-FAPROTAX-002 | P1 reproduced/code | subtract_group parsed as group header; chloroplast/nonphotosynthetic exclusions never executed; intersection unsupported | Parse ordered group operations and evaluate membership semantics faithfully |
| WV-FAPROTAX-003 | P2 code | Unknown references/cycles silently empty, group attributes and taxon literature references discarded | Validated pure parser, explicit source diagnostics and conditional evidence detail |
| WV-FAPROTAX-004 | P2 verified | No source-specific matcher tests; strict goldens cover broad genera only; README explains erroneous exact-subsequence interpretation | Add full NCBI binomial/exclusion/operator oracle coverage and accurate inference limitations |
| WV-FAPROTAX-005 | P2 verified/code | Builder ignores kwargs/stale scaffold doc; expansion TODO, unsafe force-regeneration; no real CLI invocation example | Reference shared owners WV-EXAMPLE-001/WV-UNIPROT-006; usable docs |
| WV-FAPROTAX-006 | P3 supported inference | Full rule scan per input on event loop and no duplicate memoization | Profile first, reusable parsed immutable rule graph and bounded pure memoization if beneficial |

001 uses real bundled patterns. 002 `_load_groups` exposes bogus names
subtract_group:chloroplasts/nonphotosynthetic_cyanobacteria; bundled lines 8018/8053/8054
are actual operators, not hypothetical future syntax. No claim those bogus empty groups
currently appear in output. A chloroplast lineage also retained oxygenic photoautotrophy
labels despite the bundled subtraction rule, as shown by the retained probe. Cycles aren't observed in bundled data; parser capability gap.

## Source research and workflows

Primary [provider overview](https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/)
read 2026-10-08. Bundled data header is the explicit source grammar and redistribution
notice; no new interpretation of legal permissions here. Provider describes putative
functional profiles from taxonomic communities, 16S interpretation and known functional
clade identification. These demonstrate relevance without ranking popularity.

| Workflow | Coverage | Gap/decision |
|---|---|---|
| Annotate one organism with putative ecological functions | Sorted labels from lineage | Fix species/exclusion semantics first; preserve not-measured interpretation |
| Explain why a function was assigned | No matching rule/reference output | Conditional rule/taxon/literature evidence and group attributes |
| Convert abundance/OTU table to community functional profile | Per-taxon building block only | Separate aggregation with abundance/overlap/unassigned semantics; not a mandatory resolver feature |
| Inspect unknown/nonannotated taxa | NO_MATCH | Explain unannotated is not demonstrated absence of function |

## Complete checklist

- **Capabilities/connectivity:** single local describe_ecology, lineage input; one
  leaf list group, no params/fan identifiers. It chains correctly from NCBI lineage.
  Rank/name normalization must preserve taxonomic specificity and avoid substring false hits.
- **OOP/functional:** current thin shared runtime appropriate. Pure source grammar
  parser→immutable ordered rule representation→membership evaluator suits this problem.
  Avoid class per group/operation or a database repository; a small interpreter is justified
  by actual add/subtract/intersect grammar, not pattern fashion.
- **Build/parity/provenance:** bundled file, no downloads/local DB/API parity required.
  Data version fingerprint documented; validate header/hash when changing data. Preserve
  verbatim embedded notice and clearly distinguish custom matcher from upstream software.
- **Correctness/errors:** sorted outputs, order/length retained; invalid lineage currently
  normalizes to miss. Rules lose metadata and don't validate refs; define configuration/source
  failures separately from valid no-match. Quoted member syntax documented by source header
  also unsupported by current startswith('*') parser; prevalence not quantified.
- **Groups/cache/batch:** one complete output group, no source IO. Input duplicates rerun
  matcher; no cap/set identity issue. Current exact behavior is deterministic but incorrect
  on real NCBI species names. No public dataclasses currently needing JSON round trips.
- **Documentation/usability:** source citation/license notice present, provider redirects
  current overview. Explain predicted/putative taxonomy inference, missing annotation,
  overlaps and limits. Add CLI/Python execution example, source update/oracle instructions.
- **Tests/releases:** eight passed, zero skipped; strict passes broad-family goldens.
  Only conformance/contract files, no dedicated rule unit suite. Add actual species,
  subtract/intersect ordered semantics, missing refs/cycles, quoted syntax and false positives.
  Never weaken contracts; correctness patch version sites/data unchanged unless necessary.

[Backend](../../../weavers/faprotax_weaver/src/faprotax_weaver/backends/local.py),
[bundled grammar](../../../weavers/faprotax_weaver/src/faprotax_weaver/data/FAPROTAX.txt),
[contract examples](../../../weavers/faprotax_weaver/tests/test_contract.py).
Offline probes only; reference upstream matcher differential run proposed, not completed.
[Spec](faprotax.spec.md), [plan](faprotax.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.

[Retained offline reproduction](../reproductions/weaver_faprotax.py) runs without network;
all database writes stay in temporary directories.
