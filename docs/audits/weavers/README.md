# Individual weaver audits

Programme: [plan](../weavers.plan.md), [GitHub #147](https://github.com/rafaelmdc/braidworks/issues/147).
Audit date: 2026-10-08. Branch: `audit/individual-weavers`. Implementation proposals
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
| 10 | BacDive | Planned | — | — |
| 11 | AGORA | Planned | — | — |
| 12 | FAPROTAX | Planned | — | — |
| 13 | Disbiome | Planned | — | — |
| 14 | GMrepo | Planned | — | — |
| 15 | MONDO | Planned | — | — |
| 16 | Wikidata | Planned | — | — |
| 17 | Wikipedia | Planned | — | — |

Evidence refers to the source revision recorded in each report. No live database
research is required for the bundled teaching Example. Real-source research must
distinguish supported workflows from claims about frequency of use.
