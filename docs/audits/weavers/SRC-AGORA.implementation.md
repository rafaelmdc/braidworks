# AGORA source audit implementation

Issues #249, #254; version 0.2.7; core 0.21.6. Local branch `fix/source-audit-pack-10`.

Individual model artifacts are stream-validated as complete SBML XML with an identified model. Downloads use existing core per-target locks, temporary staging, validation and atomic publication. Invalid cached files are not returned; failed replacements preserve original files. Safe reconstruction IDs prevent escaping the configured cache directory. This is structural validation, not complete SBML schema/biochemical validation.

Model output retains local path and portable source URL, and adds release, observed model ID and content SHA256. Backend fingerprints include model directory, download policy and artifact stat identities alongside reaction/source identity. Directory and availability changes invalidate cached lookup identity. Hashing all multi-MB files is deliberately avoided during fingerprinting; exported models carry content hashes.

CC-BY-NC-4.0 is recognized in core while retaining restricted classification. Reference rendering explicitly retains attribution and noncommercial limits. Unknown licenses retain conservative handling. AGORA requires core>=0.21.6; source terms are unchanged. [Creative Commons terms](https://creativecommons.org/licenses/by-nc/4.0/) were checked.

Tests exercise malformed/HTML/truncated downloads, invalid existing files, failed-replacement preservation, concurrent single acquisition, state changes, hashes and path safety. Existing non-contract model fixture was strengthened from fake non-model XML to an identified model; contract suites were preserved.

**Live limitation:** the opt-in single model test failed because VMH's configured URL returned a 12,130-byte HTML application page instead of SBML. Same-helper inspection confirmed this response. No invalid model was published. This source-acquisition defect is separately tracked in #298, which remains a correctness follow-up requiring research rather than user scope approval. Model/reaction bridge proposals remain #251.

## Verification

Package suite: **44 passed, 1 opt-in skip**. Strict verification passed. Repository lint passed. Full workspace result is recorded in the batch report after completion.

Repository validation: `make test` passed (2094 pytest tests, 56 opt-in skips, plus 5 tool unittest checks); `make lint` passed. Tooling used the isolated audit environment.

## Acquisition follow-up #298 — research update (2026-10-10)

The official [AGORA2 repository](https://github.com/VirtualMetabolicHuman/AGORA2)
still directs dataset acquisition to VMH. A search result retained an indexed
AGORA2 directory, but opening the current
[2.01 release directory](https://www.vmh.life/files/reconstructions/AGORA2/version2.01/)
returned HTTP 404 through the browsing tool. The reconstruction-download page was
also inaccessible to that tool. These observations are evidence of unresolved
acquisition, not proof that individual files are permanently unavailable.

No replacement endpoint was verified, no release/mirror was substituted, and no
large archive was downloaded. #298 remains open. Existing SBML validation still
rejects HTML and prevents publication of an invalid downloaded model.
