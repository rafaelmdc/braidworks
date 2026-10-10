# Disbiome implementation record

## Exact identity routing — #262 (partial)

Version 0.3.5 accepts either registered `ncbi.taxon.id` or the existing
`ncbi.taxon.species_id`. A supplied generic identity takes precedence. A miss
never falls back to an ancestor or the other identity. Genus observations are
reachable without mislabelling them as species observations. Full records retain
provider organism identity; missing source rank remains unknown rather than inferred.

Regression tests cover Enterococcus taxid 1350 through the generic input and
conflicting generic/species inputs without fallback. Existing species callers
remain covered by the unchanged behavior tests. Package suite: 33 passed,
1 opt-in live skipped; strict verification and workspace lint passed.

Issue #262 remains open pending explicit rank coverage/provenance in the build
validation work (#265). Ancestor roll-up is optional and remains out of scope.

## Source integrity — #265

Version 0.3.6 validates table/row shapes, unique positive primary IDs, present
foreign references, and valid positive SQLite-range experiment taxids before
opening the destination. Nullable references are retained with explicit missing
coverage. SQL additionally enforces unique non-null experiment identities.
Normalized ID joins work across integer/string source representations.

Build metadata retains per-table observed counts/hashes, missing-reference counts,
completion time, and the non-frozen snapshot limitation. This does not invent a
release identifier or claim cross-table temporal consistency. Existing schema-2
caches remain readable; refreshed caches carry the new provenance.

Eleven new regressions verify malformed source rejection without destination changes
and truthful nullable-join coverage. Package suite: 44 passed, 1 live skipped;
strict verification and workspace lint passed. No HTTP backend changed.

Final complete workspace validation: 2102 pytest cases passed, 56 skipped, plus
five tool unittest checks. Workspace lint and strict verification passed.

Five additional source-identity regressions passed in the final 44-test Disbiome
package run; they were added after the workspace run reached Disbiome.
