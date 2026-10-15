# Explicit source coverage — #135

## Decision

Implement the issue's smaller alternative: AGORA exposes the taxids observed in its
bundled crosswalk. Callers can intersect related IDs before asking for reconstruction
records. Do not add automatic downstream coverage predicates to the executor.

Automatic pruning cannot be justified by a generic weaver-wide membership set: coverage
can differ by capability, output group, backend, release and fallback path. Crosswalk
membership does not prove reaction or SBML availability. A false negative would erase
real results, and pruning could also discard outputs needed by sibling branches.

## Contract and plan

Add `agora_weaver.crosswalk_taxids() -> frozenset[int]`, derived from the same bundled
index used by reconstruction lookups. Use canonical integer taxids, no hard-coded counts,
no mutable cached return and no network/database acquisition. The corresponding source
release is `agora_weaver.dataset.CROSSWALK_RELEASE`. Document exact-taxid membership;
no ancestor/descendant inference, species promotion or reaction/model guarantee.

Callers explicitly filter their observed ID collections before constructing downstream
inputs; the planner/executor do not change behavior. Unknown coverage from other sources
must never be treated as an empty universe. Test equality with source lookups, immutable
return, canonical input intersection and false guarantees. Bump AGORA's three version
sites using scratch-generated vocab; run its suite and strict gate, then docs checks.

## Acceptance

Implemented 2026-10-15. `crosswalk_taxids()` is exported from the package and returns
canonical immutable exact membership from the lookup index. Tests compare the complete
bundled universe to lookup data and check explicit intersections without acquisition.
AGORA: 57 passed, one live skip; strict conformance/golden and workspace lint passed.
Scratch-generated vocab differed only in the reviewed patch version. Documentation
checked 1,290 links/anchors in 243 documents; whitespace passed. Automatic executor
pruning is intentionally not implemented; the issue's explicit-source alternative is.
