# gmrepo source correctness implementation

Issue #271; package version 0.2.7. Implemented locally on `fix/source-audit-correctness-batch`.

Private pure normalization validates finite percentages in [0,100] and exact nonnegative counts within SQLite's integer range. Boolean, fractional counts, NaN, infinities and invalid strings fail explicitly with the field and original value. Missing measurements remain None; prevalence with no valid runs remains undefined rather than zero. Sample counts cannot exceed the corresponding valid-run count.

The same validation applies to acquisition and caller-supplied builds before database creation. Existing duplicate-identity conflicts retain diagnostic priority. Tests cover invalid numeric evidence, exact large integer preservation, valid boundaries, missing values and preservation of the absent target on rejected builds.

Units were checked against the [GMrepo v2 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC8728112/) and [provider prevalence documentation](https://evolgeniusteam.github.io/gmrepodocumentation/websiteandUI/microbecentricpages/). No clipping or fraction-to-percent conversion is performed.

## Verification

Package suite: **65 passed, 2 skipped**. Strict verification and repository checks are recorded with the issue closure. Other source findings remain open; this report closes only the issue named above.

Repository verification: `make lint` passed; `make test` passed (2045 pytest cases, 56 opt-in skips, plus the tool unittest suite). `weaverkit verify --strict` passed for this package. All tooling used the isolated audit environment.

## Approved retained run metadata — #272

Version 0.2.8 retains observed run listing rows in the acquisition manifest,
already covered by the local content hash. The requested metadata group reports
source rows and selection/profile coverage without new per-run requests. Empty
and failed profiles do not erase metadata; default profile coverage omits the
metadata blob. Existing databases remain readable and truthfully report absent
metadata, so no unrelated SQLite schema migration is needed. Standalone run
drilling, new disease bridges and cohort filters remain deferred.

Verification: 66 package tests passed, strict verification passed; three live
bounded acquisition checks passed. Tests cover unchanged defaults, retained
metadata for empty/failed profiles, cap/denominator context and request counts.
