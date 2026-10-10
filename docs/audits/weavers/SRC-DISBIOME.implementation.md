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
