# gtdb source correctness implementation

Issue #237; package version 0.2.9. Implemented locally on `fix/source-audit-correctness-batch`.

Newick parsing requires complete input, nonempty unique leaf labels and finite nonnegative provided branch lengths, including finite cumulative depth. Missing lengths remain zero, and optional semicolons and quoted labels remain supported. Forest loaders reject labels repeated across trees instead of silently overwriting them.

Pinned tree acquisition validates syntax and usable leaf identity as well as the checksum before publication; a malformed checksum-valid download leaves an existing tree intact. Tests cover malformed syntax, empty trees, negative/non-finite/overflow geometry, duplicate labels, valid dialect cases and failed replacement. This establishes structural leaf coverage, not a new guarantee that every crosswalk genome occurs in a reference tree.

The separate cross-tree/release comparability contract (#234) and additional capability/documentation scope (#240) remain open.

## Verification

Package suite: **86 passed, 3 skipped**. Strict verification and repository checks are recorded with the issue closure. Other source findings remain open; this report closes only the issue named above.
