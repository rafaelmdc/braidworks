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
| 1 | #193 | PDBe range normalization and optional quality summary | Complete minimum: 63 tests, strict, 6 live |
| 1 | #240 | GTDB representative accession/release group; no tree changes | Complete: 88 tests, strict, 2 live API checks |
| 1 | #264 | Disbiome compact evidence identity | Complete minimum: 46 tests and strict |
| 1 | #296 | Disbiome exact sample/method/outcome filters | Complete: 46 tests and strict |
| 1 | #295 | Wikipedia observed monthly series/title provenance | Complete: 39 tests, strict, 2 live |
| 1 | #297 | FAPROTAX ordered rule explanation group | Complete: 33 tests, strict, 25,068 reference cases without mismatch |
| 1 | #272 | Retain already-returned GMrepo run metadata | Complete minimum: 66 tests, strict, 3 live |
| 1 | #219 | STRING score/functional/physical/species scope | Complete: 64 tests, strict, 4 live |
| 2 | #206 | QuickGO filters, raw evidence and explicit negative semantics | Complete minimum: 75 tests, strict, 6 live |
| 2 | #207 | QuickGO typed relations/obsoletion group | Complete minimum: 75 tests, strict, 6 live |
| 2 | #212 | Reactome hierarchy and typed participant groups | Complete minimum: 62 tests, strict, 4 live |
| 2 | #231 | NCBI current/merged/deleted identity evidence; accurate docs | Complete minimum: 228 package tests, 7 targeted, strict |
| 2 | #246 | BacDive strain list/describe; accurate group/scope docs | Complete minimum: 65 tests, strict, 3 live |
| 2 | #251 | AGORA reconstruction list/describe with artifact availability | Complete minimum: 46 tests and strict |
| 2 | #278 | Direct MONDO-ID describe, definition and history | Complete minimum: 57 tests and strict |
| 2 | #286 | Wikidata exact ID entry and localized labels; English join preserved | Complete minimum: 54 tests, strict, 3 live |

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

Pack 1 registry verification corrected a missing canonical string declaration for
`structure.alphafold.model_id` and cataloged all six new leaf outputs. Core 0.21.7
and weaverkit 0.6.10 include those declarations; no scientific logic was added to
core. Core's 541 tests and weaverkit's 291 tests pass with the existing contracts.
Final workspace validation is recorded below.

Workspace checkpoint after pack 1 and QuickGO's initial pack-2 changes:
`make lint` passed; `make test` passed with **2,129 pytest cases, 63 opt-in skips,
and five tool unittests**. Index regenerated without uncataloged pack-1 outputs.
The full test run includes QuickGO's initial code; its six opt-in live checks
were run separately and passed. Pack-2 changes after this checkpoint require
fresh final workspace validation.

Final verification of the approved scopes: `make test` passed with **2,149
pytest cases, 69 opt-in skips, and five tool unittests**. `make lint` and strict
verification of all **17 weavers** passed. The final BacDive review adds one
regression (65 package tests total) for malformed type-strain flags and exact-strain
conflict warnings; its three live tests passed again after that correction.
Changed HTTP packages passed 37 distinct live E2E cases across ten weavers; these
are bounded known-truth checks, not exhaustive upstream guarantees.

All 18 approved minimum scopes are complete. GitHub issues #199, #206, #286,
#295, #296 and #297 are closed; broader findings retain their implementation
comments and deferred scope. #234, release/publishing #142, persistent cache/resume
#143 remain deferred. AGORA acquisition #298 was subsequently fixed and closed
(see nondeferred-completion.plan.md). Changes are on
`feat/weaver-audit-approved-scopes` as local commits; nothing was pushed or released.
