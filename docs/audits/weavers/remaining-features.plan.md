# Finish the remaining feature issues

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
| 7 | #207 | QuickGO hierarchy/replacements and bounded reverse annotations | Complete: 77 tests, strict, seven live checks |
| 8 | #212 | Reactome recursive reactions/evidence | Complete: 65 tests, strict, five live checks |
| 9 | #193 | PDBe entity/alignment/assembly/ligand/coordinate workflows | Complete: 65 tests, strict; six live checks pass, one transient skip |
| 10 | #240 | GTDB genome quality/synonym/release history (no tree-distance changes) | Pending |
| 11 | #202 | AlphaFold archive-only fragment exploration | Pending |

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
