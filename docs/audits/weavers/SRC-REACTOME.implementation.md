# REACTOME source audit implementation

Issues #214; version 0.1.12. Local branch `fix/source-audit-pack-10`.

Listing records retain species, inferred-status and the complete observed source row. Missing fields remain unknown; no database version is inferred from releaseDate or an endpoint fingerprint. Identical duplicate stable IDs collapse. Any conflicting duplicate row is an explicit source error independent of input order, rather than silently selecting the first. Source metadata projection adds no request and preserves stable-ID fan-out.

Live E2E: known TP53 listing passed; malformed-accession and pathway-description cases skipped on upstream transient failures. A separate bounded direct probe timed out/returned HTTP403. This is partial live evidence, not full upstream certification. Listing tests cover retained evidence, unavailable release fields and conflicts in multiple permutations. [Provider Content Service documentation](https://reactome.org/dev/content-service) describes curated/inferred pathways. New hierarchy/participant capability scope remains #212.

## Verification

Package suite: **60 passed, 3 opt-in skips**. Strict verification passed. Repository lint passed. Full workspace result is recorded in the batch report after completion.

Repository validation: `make test` passed (2094 pytest tests, 56 opt-in skips, plus 5 tool unittest checks); `make lint` passed. Tooling used the isolated audit environment.
