# Individual weaver audits

Programme: [plan](../weavers.plan.md), [GitHub #147](https://github.com/rafaelmdc/braidworks/issues/147).
Audit date: 2026-10-08. S01–S03 complete locally; S04 review pending. Branch: `audit/individual-weavers`. Implementation proposals
are not accepted or implemented merely because an audit is complete.

| Order | Weaver | Status | Main findings | Documents |
|---|---|---|---|---|
| 01 | Example | Audited locally | Unsafe stale regeneration instructions; ignored configuration; teaching/test gaps | [Report](example.audit.md), [spec](example.spec.md), [plan](example.plan.md) |
| 02 | UniProt | Audited locally | Exact-ID selection, mapping duplicates/group coverage, malformed payloads, lifecycle and annotation gaps | [Report](uniprot.audit.md), [spec](uniprot.spec.md), [plan](uniprot.plan.md) |
| 03 | PDBe | Audited locally | Source/limit identity, response validation and structure-detail coverage | [Report](pdbe.audit.md), [spec](pdbe.spec.md), [plan](pdbe.plan.md) |
| 04 | AlphaFold | Audited locally | Fragment coverage, response validation and confidence/model-list gaps | [Report](alphafold.audit.md), [spec](alphafold.spec.md), [plan](alphafold.plan.md) |
| 05 | QuickGO | Audited locally | Single-input correlation, coverage identity and ontology/filter gaps | [Report](quickgo.audit.md), [spec](quickgo.spec.md), [plan](quickgo.plan.md) |
| 06 | Reactome | Audited locally | Limit/source identity, response validation and hierarchy/detail gaps | [Report](reactome.audit.md), [spec](reactome.spec.md), [plan](reactome.plan.md) |
| 07 | STRING | Audited locally | Stable partner identity, restricted coverage, duplicate edges and mutable version | [Report](string.audit.md), [spec](string.spec.md), [plan](string.plan.md) |
| 08 | NCBI | Audited locally | Unsafe direct rebuild, broken build CLI, silent enrichment failure and ambiguity | [Report](ncbi.audit.md), [spec](ncbi.spec.md), [plan](ncbi.plan.md) |
| 09 | GTDB | Audited locally | Crosswalk ambiguity, disconnected tree distance, release bundles and build validation | [Report](gtdb.audit.md), [spec](gtdb.spec.md), [plan](gtdb.plan.md) |
| 10 | BacDive | Audited locally | Representative identity, scan coverage, duplicate work and strain capabilities | [Report](bacdive.audit.md), [spec](bacdive.spec.md), [plan](bacdive.plan.md) |
| 11 | AGORA | Audited locally | Unavailable group completion, model artifact safety and model bridges | [Report](agora.audit.md), [spec](agora.spec.md), [plan](agora.plan.md) |
| 12 | FAPROTAX | Audited locally | Binomial matching and subtraction grammar correctness | [Report](faprotax.audit.md), [spec](faprotax.spec.md), [plan](faprotax.plan.md) |
| 13 | Disbiome | Audited locally | Genus/species input mismatch, evidence identity and projection cost | [Report](disbiome.audit.md), [spec](disbiome.spec.md), [plan](disbiome.plan.md) |
| 14 | GMrepo | Audited locally | Silent failed acquisition, cohort coverage and duplicate/invalid data | [Report](gmrepo.audit.md), [spec](gmrepo.spec.md), [plan](gmrepo.plan.md) |
| 15 | MONDO | Audited locally | Ambiguous mapping precision, cyclic traversal and direct-ID gaps | [Report](mondo.audit.md), [spec](mondo.spec.md), [plan](mondo.plan.md) |
| 16 | Wikidata | Audited locally | SPARQL shape validation, stable aliases and source configuration | [Report](wikidata.audit.md), [spec](wikidata.spec.md), [plan](wikidata.plan.md) |
| 17 | Wikipedia | Audited locally | Metric parity, inclusive windows, month reuse and response validation | [Report](wikipedia.audit.md), [spec](wikipedia.spec.md), [plan](wikipedia.plan.md) |

Evidence refers to the source revision recorded in each report. No live database
research is required for the bundled teaching Example. Real-source research must
distinguish supported workflows from claims about frequency of use.

[Priorities and dependencies](summary.md) · [all33 capability contracts and interface assessment](coverage.md) · [full findings table (TSV)](findings.tsv) · [offline reproductions](../reproductions/README.md).

Research confidence: all 16 real sources have primary-source workflow evidence;
reports distinguish full page reads, indexed text and live observations. Example is
a teaching fixture. No usage-frequency rankings or full live certification claimed.

[GitHub issue hierarchy and second-pass grouping review](issue-hierarchy.md).


Implementation progress: shared group #152 (atomic database replacement) and
#150 (validated responses and isolated failure values) are complete locally.
See [SH-03 implementation evidence](SH-03.implementation.md) for #150's fifteen
findings, migration notes and validation. Remaining groups retain their own scope.
