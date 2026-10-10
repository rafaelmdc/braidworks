# ALPHAFOLD source audit implementation

Issues #197; version 0.1.9. Local branch `fix/source-audit-pack-10`.

The preferred F1 selection stays intact, but selected records now retain 1-based inclusive UniProt range, source sequence length, model length, fragment number and full/partial/unknown coverage. Partial coverage warns even for scalar-only requests. Malformed source ranges become isolated error records. Real observed P04637 ranges were added to the spec sample and fixture. Synthetic long-protein F1 and unknown-coverage tests prevent treating an ID suffix as proof of complete coverage.

Live E2E: both known TP53 coverage and malformed-accession cases passed. Coverage reflects source-provided sequence/range metadata; alternative models and raw confidence outputs remain #199/#202. Provider [fragment documentation](https://alphafold.ebi.ac.uk/download) explains overlapping long-protein fragments.

## Verification

Package suite: **42 passed, 2 opt-in skips**. Strict verification passed. Repository lint passed. Full workspace result is recorded in the batch report after completion.

Repository validation: `make test` passed (2094 pytest tests, 56 opt-in skips, plus 5 tool unittest checks); `make lint` passed. Tooling used the isolated audit environment.

## Approved confidence references — #199

Version 0.1.10 adds requested `structure.alphafold.confidence`: observed PAE and
per-residue pLDDT JSON URLs, model/version/coverage and metric semantics. Missing
URLs stay null; no linked files are fetched. Existing outputs and representative
selection are unchanged. 44 package tests passed, strict verification passed, and
all 3 live E2E tests passed. Parsed matrices/vectors remain outside this scope.
