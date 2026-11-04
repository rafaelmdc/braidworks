# STRING source audit implementation

Issues #221; version 0.1.12. Local branch `fix/source-audit-pack-10`.

Mapping explicitly requests echo_query=1 while retaining validated query-index fallback. Each request identifies braidworks. Existing distinct-ID chunks of 100, chunk-local failures, safe regeneration and owned/borrowed lifecycle contracts remain intact. The paced client defaults to one request per second when explicit executor/environment budgets are absent, following the [provider recommendation](https://en.string-db.org/help/api/). Documentation includes the bulk contract, source limitations, functional-association semantics and an executable context-managed Python example.

Live E2E: all three known-truth, miss and pinned-release tests passed. New tests assert explicit echo/caller settings, a single bulk request and the default source rate. Network/species/score parameters remain #219; a physical-interaction claim is not inferred from functional edges.

## Verification

Package suite: **58 passed, 3 opt-in skips**. Strict verification passed. Repository lint passed. Full workspace result is recorded in the batch report after completion.

Repository validation: `make test` passed (2094 pytest tests, 56 opt-in skips, plus 5 tool unittest checks); `make lint` passed. Tooling used the isolated audit environment.

## Approved interaction scope — #219

Version 0.1.13 adds validated score, network type and species parameters.
Both acquisition stages remain bulk requests; conflicting returned species is
an error rather than silently mixing taxa. Coverage states effective settings
and score units. Default functional behavior and retrieval limits are preserved.

Verification: 64 package tests passed, four opt-in skips; strict verification
and four live checks passed, including physical TP53 interactions at threshold
700 and species 9606.
