# Approved recommendation implementation

User approval: 2026-10-10, implement the researched recommendations except #234.
Source: [research review](recommendation-research.md). Implement the minimum scopes
and preservation boundaries reviewed there. Explicitly deferred expansions remain
deferred; broad original issues stay open when their remaining scope is not done.
#234, publishing #142 and durable cache/resume #143 remain untouched.

Branch: `feat/weaver-audit-approved-scopes`; local commits, no push.
No environment/global installation is needed. Use the isolated audit venv.

| Pack | Issue | Approved scope | Status |
|---|---|---|---|
| 1 | #199 | Observed AlphaFold PAE/pLDDT reference group | Complete: 44 package tests, strict, 3 live |
| 1 | #202 | API-observed model list/describe and truthful coverage | Complete: 47 package tests, strict, 4 live |
| 1 | #193 | PDBe range normalization and optional quality summary | Pending |
| 1 | #240 | GTDB representative accession/release group; no tree changes | Complete: 88 tests, strict, 2 live API checks |
| 1 | #264 | Disbiome compact evidence identity | Pending |
| 1 | #296 | Disbiome exact sample/method/outcome filters | Pending |
| 1 | #295 | Wikipedia observed monthly series/title provenance | Complete: 39 tests, strict, 2 live |
| 1 | #297 | FAPROTAX ordered rule explanation group | Complete: 33 tests, strict, 25,068 reference cases without mismatch |
| 1 | #272 | Retain already-returned GMrepo run metadata | Pending |
| 1 | #219 | STRING score/functional/physical/species scope | Pending |
| 2 | #206 | QuickGO filters, raw evidence and explicit negative semantics | Pending |
| 2 | #207 | QuickGO typed relations/obsoletion group | Pending |
| 2 | #212 | Reactome hierarchy and typed participant groups | Pending |
| 2 | #231 | NCBI current/merged/deleted identity evidence; accurate docs | Pending |
| 2 | #246 | BacDive strain list/describe; accurate group/scope docs | Pending |
| 2 | #251 | AGORA reconstruction list/describe with artifact availability | Pending |
| 2 | #278 | Direct MONDO-ID describe, definition and history | Pending |
| 2 | #286 | Wikidata exact ID entry and localized labels; English join preserved | Pending |

For each change: read current implementation/tests, update spec and observed source
samples where needed, implement with small projections/composition, add meaningful
regressions for preservation boundaries, patch-bump all three weaver version sites,
selectively regenerate vocab, update lock/docs and commit. New bridge keys are
registered with producer/consumer semantics; toolkit behavior changes get a toolkit
version bump. Do not rewrite core or relax contracts.

Run package tests and strict verification for each changed package. Changed HTTP
backends also require opt-in live E2E; document genuine upstream failures without
claiming verification. Run workspace lint/test and regenerate indexes at pack
boundaries. Report exact checks and remaining/deferred scopes on GitHub.
