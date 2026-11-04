# Acquisition progress and bounded network waits — #131

## Current evidence

The report predates the current GTDB adapter. Its API client has a 30-second timeout,
no retry/backoff loop, and bounded concurrent requests. Core already defaults to
local-first routing and supports explicit backend policies and fallback on errors.
No current evidence reproduces the reported unbounded API retry. Existing valid GTDB
crosswalks return from setup without downloading unless refresh/release selection asks
for a replacement.

Two shared acquisition gaps remain: `download` and the optional checksum request use
urllib without an explicit socket timeout; `ensure_local_db` and downloads without a
callback can be silent. Build locks have a finite timeout but setup does not report
waiting. These are the implementation scope, rather than inventing a new retry system.

## Contract and plan

1. Bound download/checksum socket operations to 30 seconds by default. Allow a finite,
   positive download timeout override. This is an inactivity/socket timeout, not a total
   deadline for a multi-GB transfer. No automatic retries are added.
2. Emit initial, periodic (at most once per ten seconds), completed and failed progress
   to stderr when no callback is supplied. Show bytes/total when available; omit URLs
   and exception text that could expose signed URLs. Existing callbacks replace this
   reporter, including a no-op callback for quiet operation.
3. Report acquisition/build and lock waiting using the same callback contract. Valid
   existing artifacts remain silent. Preserve consent, atomic replacement, exception
   propagation and the old artifact on failure.
4. Test startup before blocking, progress without Content-Length, timeout propagation,
   quiet/custom callbacks, failed builds and unchanged valid-artifact behavior. Run
   core and source setup suites through workspace targets; no live/download acquisition.
5. Document exact limits and stderr behavior, patch-bump core, update the lockfile,
   commit and close #131 after verification.

## Acceptance

Implemented and verified 2026-10-15. Lint passed; core 568 tests and toolkit 295 tests
passed. All seven weaver suites using shared acquisition passed: NCBI 236, GTDB 91,
AGORA 55, MONDO 62, GMrepo 69, Disbiome 48 and Wikipedia 39 (27 live/optional skips).
Tests used fixtures and mocked transfers, with no real datasets acquired. Local links
and whitespace checks passed. A failed refresh preserves the old published artifact.

The old 33-minute incident cannot be reconstructed without its application registry
and upstream condition. This closes the verified acquisition gaps; it does not claim
a total deadline for arbitrary source parsing/build callbacks or large active transfers.
