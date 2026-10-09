# SRC-EXAMPLE — teaching reference correctness and usability

Group #157; branch `fix/example-weaver-reference`.

| Finding | Issue | Result |
|---|---|---|
| WV-EXAMPLE-003 | #176 | README explains intentional scaffold differences, explicit registration, illustrative data limits, string Celsius values, mapping/cache behavior and a complete asynchronous batch with a miss and duplicate. |
| WV-EXAMPLE-004 | #177 | Contract samples now contain all five bundled real taxids. The shared contract implementation and checks are unchanged. New focused cases verify known values, miss position, duplicate position, requested-only outputs and detached backend projections. |
| WV-EXAMPLE-005 | #178 | Spec and selectively regenerated vocab identify the canonical repository CSV URL. Package/spec/vocab are patch-bumped together to 1.0.5; lockfile is updated. |
| WV-EXAMPLE-006 | #179 | Optional pure-parser extraction remains pending a scope decision; no parser or public API change is claimed. |

The three accepted fixes need no new architecture. CSV I/O/parsing remain in the
small existing private loader; the backend copies cached values into records and
core performs output filtering. No new repository, strategy or record hierarchy,
external source or automatic discovery is introduced. Existing supported callers
need no migration. The source URL correction affects reference metadata only.

Verification: package suite passes (21 tests); strict verification passes all
conformance/golden/placeholder checks. The README Python block executes offline and
returns negative, positive, NO_MATCH and negative with only gram-stain strands.
All five bundled IDs and both output selections pass focused checks. No API backend
was touched, so live-service checks are unnecessary. Workspace lint and full tests pass: 1933 pytest tests plus five unittest tests,
53 skipped. git diff --check passes.

The fabricated order samples were deliberately replaced with real successful
inputs as required by #177, strengthening coverage without weakening or removing
any shared contract/conformance check. Generated vocab was selectively copied from
scratch generation; the implemented backend is unchanged.
