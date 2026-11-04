# Complete non-deferred weaver findings

Current status (2026-10-10): the owner subsequently approved all eleven residual
expansions listed below. They are now complete and closed; see
[final feature acceptance](remaining-features.plan.md). The deferral language and
validation counts below describe the earlier checkpoint. Only #234, #142 and #143
remain excluded from this pass.

User instruction: finish the issues, at least the non-deferred ones (2026-10-10).
This supersedes stopping after the approved minimum scopes. Complete outstanding
acceptance work and reconcile broad historical issue titles against delivered
behavior. Do not turn an explicit research deferral into silently approved scope.
#234, publishing #142 and durable cache/resume #143 remain excluded. Other
expansions explicitly deferred in recommendation-research.md stay identifiable.

| Issue | Outstanding action | Status |
|---|---|---|
| #219 | Reconcile completed supported parameters and scientific semantics | Closed |
| #262 | Explicit exact-match organism/rank coverage; no ancestor inference | Closed: 8401ea7, 47 tests and strict pass |
| #298 | Verify pinned provider individual acquisition, or expose truthful unavailability | Implemented: explicit VMH agora2_2.01 service; 52 tests, strict and live pass |
| Remaining broad findings | Compare actual acceptance criteria with implementation; separate deferred residual scope | Reconciled all 11 broad issues; original evidence preserved |
| Source group / programme issues | Close only when every child is complete; list deferred children | Closed #163, #168, #172, #173; reconciled remaining group and #147 checkboxes |

Work stays on feat/weaver-audit-approved-scopes, with local commits and GitHub
updates. No push, release or tags. API changes need live checks; source acquisition
must not fall back to arbitrary mirrors or multi-GB downloads.

AGORA acquisition evidence (2026-10-10): the obsolete static www route returned
HTML and non-www returned 404. VMH's current reconstructionDownload page uses
/api/getMicrobeReconstructions; metadata for the explicit agora2_2.01 family
identifies AGORA2 version 2.01. The corresponding format=sbml response is
1,142,776 bytes and validates as model microbe_1261. It is service-generated
SBML rather than byte-identical archive XML. The package live download test
passed without relaxing validation or acquiring an archive. Endpoint configuration
affects fingerprints and exported URLs; cached-file provenance remains unverified.

Primary sources: [current provider download page](https://vmh.life/reconstructionDownload),
[explicit release-selected metadata](https://vmh.life/api/getMicrobeReconstructions?id=Abiotrophia_defectiva_ATCC_49176&version=agora2_2.01).
Probes and downloaded model remain under ignored .audit-local; no data committed.

## Residual feature scope

GitHub titles/bodies now distinguish completed implementation from remaining scope:

| Issue | Remaining expansion from the research review |
|---|---|
| #193 | PDBe assemblies/ligands/full alignment and entity mapping |
| #202 | AlphaFold archive-only fragments |
| #207 | Additional QuickGO hierarchy and reverse annotations |
| #212 | Reactome recursive reactions/full evidence |
| #231 | NCBI local descendants |
| #240 | GTDB genome quality/synonyms/history |
| #246 | BacDive normalized culture/genome mappings |
| #251 | AGORA genome/reaction routing bridges |
| #264 | Disbiome reverse disease bridge |
| #272 | GMrepo standalone run/cohort/phenotype workflows |
| #278 | MONDO release-matched typed SSSOM ingestion |

These residual issues remain open; implemented portions are checked against current
code and tests, not re-counted as outstanding defects. An optional scope question
asks whether to bring those research-separated expansions into implementation;
existing deferrals remain in force pending steering. Older standalone product
backlog issues are separate from this weaver-audit completion pass.

Final verification: full workspace test run passed (2,153 pytest cases, 69
opt-in skips, five tool unittests). Subsequent endpoint-configuration validation
passed the complete 52-test AGORA suite; its three model-workflow checks, including
the live download, passed after the endpoint option was added. Workspace lint and
all 17 strict weaver gates passed. Final local commits: 8401ea7 (Disbiome) and
270accc (AGORA). No push.
