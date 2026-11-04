# Finish the remaining feature issues

Delivery update (2026-10-10): the owner authorized pushing and closing completed
trackers. The implementation through `58a1420` is pushed to
[feat/weaver-audit-approved-scopes](https://github.com/rafaelmdc/braidworks/tree/feat/weaver-audit-approved-scopes).
Completed #136–#141 and #144–#146 are closed. Deferred #234, #142 and #143,
parents #165/#147, and the older standalone backlog remain open. Local-only and
no-push statements below describe the preceding acceptance checkpoint. No merge,
tag or package publication was performed. The current CI workflow runs for PRs
and pushes to main; this branch-only push does not start remote CI.

User instruction (2026-10-10): implement the remaining issues, including the larger
expansions previously separated in recommendation-research.md. This supersedes
those research deferrals. #234, publishing #142 and persistent cache/resume #143
remain excluded. No pushing, release tags or publication.

| Order | Issue | Full remaining scope | Status |
|---|---|---|---|
| 1 | #231 | NCBI local descendant parity | Complete: 231 tests and strict |
| 2 | #272 | GMrepo standalone run/cohort/phenotype workflows | Complete: 69 tests, strict, four live checks |
| 3 | #264 | Disbiome reverse disease bridge with exact observed taxa | Complete: 48 tests and strict |
| 4 | #246 | BacDive culture/genome identifiers with multiplicity | Complete: 68 tests, strict, four live checks |
| 5 | #251 | AGORA genome/reaction routing bridges | Complete: 55 tests and strict |
| 6 | #278 | MONDO release-matched typed SSSOM ingestion | Complete: 62 tests, strict, observed tagged SSSOM |
| 7 | #207 | QuickGO hierarchy/replacements and bounded reverse annotations | Complete: 79 tests, strict, seven live checks |
| 8 | #212 | Reactome recursive reactions/evidence | Complete: 65 tests, strict, five live checks |
| 9 | #193 | PDBe entity/alignment/assembly/ligand/coordinate workflows | Complete: 65 tests, strict; six live checks pass, one transient skip |
| 10 | #240 | GTDB genome quality/synonym/release history (no tree-distance changes) | Complete: 91 tests, strict, two lightweight live checks |
| 11 | #202 | AlphaFold archive-only fragment exploration | Complete: 51 tests, strict, bounded real archive header probe |

Implement one coherent source contract at a time. Keep source-specific projections
pure where useful; use existing lookup/resolver mappers and optional protocols,
not a new class hierarchy. Observe provider payloads before designing mappings.
Bulk APIs when available; use concurrency for single-ID endpoints. Full distinct
fan sets are independent of display caps. Acquisition limits and incomplete source
coverage must remain explicit. Keep schema rebuild/version migrations honest.

Every package change needs package tests, strict verification, version-site bumps,
reviewed selective vocab regeneration and a local commit. API changes require live
checks. Run workspace lint/test and index at meaningful checkpoints. Close an issue
only after its acceptance is evidenced; update source parents and programme state.
Do not acquire full multi-GB archives merely to probe formats; use bounded provider
access or return to the user with a concrete unavoidable resource limitation.

Registry notes: GMrepo run identity uses core 0.21.10/toolkit 0.6.15; Disbiome
provider disease identity and canonical produced disease codes use core 0.21.11/
toolkit 0.6.16; BacDive collection identity uses core 0.21.12/toolkit 0.6.17.
These are type declarations only, with no source/domain algorithms in core.

## Final local acceptance — 2026-10-10

All eleven expansions are implemented and their finding issues closed. Native source
parent links were checked against actual children: #159–#162, #164, #166–#167 and
#169–#171 are closed. #165 remains open solely for explicitly deferred #234;
programme #147 also retains that exclusion and unrequested remote delivery.
Historical proposal/minimum-scope notes are superseded by this accepted scope.
Older standalone product backlog issues are outside this weaver-audit pass.

Workspace lint and the complete package run passed: **2,187 pytest passes, 75
opt-in skips, five tool unittests**. Final boundary regressions subsequently passed
complete affected suites: AlphaFold 51, GTDB 91 and QuickGO 79, bringing the current
aggregate to **2,190 pytest cases**. All **17 strict weaver gates** pass. Generated
catalogs contain **59 capabilities across 17 weavers**, with every new field cataloged.
Live API checks/probes are listed per row; they cover changed paths, not full upstream
certification. PDBe's mappings endpoint rejected bulk POST in a real check; the
implementation uses bounded concurrent GET there and bulk supported detail routes.
No full taxonomy/proteome downloads, coordinate extraction or large source artifacts
were required. AlphaFold's real archive probe read only 4,096 bytes.

The closing review preserved known GTDB card identity when optional history is
unavailable, normalized QuickGO hierarchy IDs consistently, and classified changed
archive source identity as structural configuration failure at fingerprint boundaries.
No conformance assertions were weakened. Source snapshots, source-local predicates,
complete fan sets versus capped displays, and explicit incomplete coverage remain
separate contracts. Small pure projections and existing dispatch/mapping/threading
helpers were reused; no generic biological framework or persistent cache was added.

All changes stay in local commits on `feat/weaver-audit-approved-scopes`. No push,
merge, release tags or publishing. #234, publishing #142 and durable cache/resume
#143 remain deferred exactly as requested.

Distribution rehearsal: all 20 wheel/sdist pairs build and pass the repository's
metadata/resource and clean isolated installation/CLI smoke checks. Temporary install
environments are removed by the checker; no system Python installation or publication.
The final QuickGO hierarchy review also confirmed complete/ancestor/path bulk endpoints
against real multi-term responses and added a four-requests-per-chunk regression.
