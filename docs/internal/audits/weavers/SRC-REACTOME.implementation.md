# REACTOME source audit implementation

Issues #214; version 0.1.12. Local branch `fix/source-audit-pack-10`.

Listing records retain species, inferred-status and the complete observed source row. Missing fields remain unknown; no database version is inferred from releaseDate or an endpoint fingerprint. Identical duplicate stable IDs collapse. Any conflicting duplicate row is an explicit source error independent of input order, rather than silently selecting the first. Source metadata projection adds no request and preserves stable-ID fan-out.

Live E2E: known TP53 listing passed; malformed-accession and pathway-description cases skipped on upstream transient failures. A separate bounded direct probe timed out/returned HTTP403. This is partial live evidence, not full upstream certification. Listing tests cover retained evidence, unavailable release fields and conflicts in multiple permutations. [Provider Content Service documentation](https://reactome.org/dev/content-service) describes curated/inferred pathways. New hierarchy/participant capability scope remains #212.

## Verification

Package suite: **60 passed, 3 opt-in skips**. Strict verification passed. Repository lint passed. Full workspace result is recorded in the batch report after completion.

Repository validation: `make test` passed (2094 pytest tests, 56 opt-in skips, plus 5 tool unittest checks); `make lint` passed. Tooling used the isolated audit environment.

## Approved direct hierarchy and participants — #212

Version 0.1.13 adds requested direct hasEvent hierarchy and typed participant
reference groups. Summary acquisition remains bulk; participant routes are
single-ID and run concurrently, deduplicated within the batch. Numeric entity
IDs include the observed provider release, not a claimed frozen source snapshot.
Absent hierarchy/participant information remains unknown. Defaults perform no
additional requests. Recursive event expansion and full evidence interpretation
remain deferred.

Verification: 62 package tests and strict passed, four live checks passed.
Live verification caught the release endpoint's text/plain content negotiation
requirement (406 with application/json); the backend now requests text/plain and
a regression asserts the header. Tests retain mixed molecule/complex types,
release scope, direct event identity, duplicate detachment and default call count.
