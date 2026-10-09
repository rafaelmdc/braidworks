# gmrepo source correctness implementation

Issue #271; package version 0.2.7. Implemented locally on `fix/source-audit-correctness-batch`.

Private pure normalization validates finite percentages in [0,100] and exact nonnegative counts within SQLite's integer range. Boolean, fractional counts, NaN, infinities and invalid strings fail explicitly with the field and original value. Missing measurements remain None; prevalence with no valid runs remains undefined rather than zero. Sample counts cannot exceed the corresponding valid-run count.

The same validation applies to acquisition and caller-supplied builds before database creation. Existing duplicate-identity conflicts retain diagnostic priority. Tests cover invalid numeric evidence, exact large integer preservation, valid boundaries, missing values and preservation of the absent target on rejected builds.

Units were checked against the [GMrepo v2 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC8728112/) and [provider prevalence documentation](https://evolgeniusteam.github.io/gmrepodocumentation/websiteandUI/microbecentricpages/). No clipping or fraction-to-percent conversion is performed.

## Verification

Package suite: **65 passed, 2 skipped**. Strict verification and repository checks are recorded with the issue closure. Other source findings remain open; this report closes only the issue named above.
