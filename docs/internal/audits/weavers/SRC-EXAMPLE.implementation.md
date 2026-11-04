# SRC-EXAMPLE — teaching reference correctness and usability

Group #157; initial branch `fix/example-weaver-reference`; parser follow-up
`fix/example-csv-parser`.

| Finding | Issue | Result |
|---|---|---|
| WV-EXAMPLE-003 | #176 | README explains intentional scaffold differences, explicit registration, illustrative data limits, string Celsius values, mapping/cache behavior and a complete asynchronous batch with a miss and duplicate. |
| WV-EXAMPLE-004 | #177 | Contract samples now contain all five bundled real taxids. The shared contract implementation and checks are unchanged. New focused cases verify known values, miss position, duplicate position, requested-only outputs and detached backend projections. |
| WV-EXAMPLE-005 | #178 | Spec and selectively regenerated vocab identify the canonical repository CSV URL. Package/spec/vocab are patch-bumped together to 1.0.5; lockfile is updated. |
| WV-EXAMPLE-006 | #179 | Approved private pure parser extracted; strict schema/duplicate-ID validation tested, cached resource loading remains separate. |

The first three fixes need no new architecture; the approved fourth extracts a
small private pure parser from cached resource loading; the backend copies cached values into records and
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
scratch generation; the backend remains a small lookup implementation.

## Approved parser follow-up (#179)

The user approved this extraction after reviewing its purpose and tradeoffs.
`_parse_table` performs no I/O, caching or public API growth. It requires exactly
three unique expected headers, complete row width, positive numeric taxids and
unique normalized decimal identity. Duplicate IDs (including leading-zero aliases),
missing/extra cells and malformed CSV quoting fail explicitly. Blank trait cells
remain absent values; a valid header without data is a valid empty table.

The loader retains one private cached table and resource reading. Expected file,
encoding and declared schema failures become one error record per batch input;
programming/cancellation faults are not caught. Existing valid row outputs, units
and lookup APIs stay the same. Package/spec/generated vocab patch-bump to 1.0.6;
DATA_VERSION remains unchanged because the bundled data did not change.

Verification: all 35 package tests pass, including 14 parser/source-failure
regressions. Strict verification, workspace lint, README execution and
git diff --check pass for the follow-up. No API or core code changed.
