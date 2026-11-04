# Platform cleanup loop — final acceptance

Verified 2026-10-15 on `docs/declaration-storage-decisions`. This branch contains the
complete sequence, based on documentation commit `d52b1a1`. Earlier issue branches are
pushed for individual review; no merge or package publication was performed.

## Issue resolutions

| Issue | Commit | Resolution |
|---|---|---|
| #132 | `a3ba228` | Declaration-aware backend diagnostics and dispatch checks |
| #131 | `bb50ba5` | Acquisition progress and finite socket inactivity limits |
| #133 | `8eb0a08` | Status-token classification and explicit failure contract |
| #135 | `35085d1` | Explicit AGORA crosswalk universe; no automatic pruning |
| #67 | `91c4f85` | Spec-generated exact inventories and CI drift checks |
| #86 | `0e02732` | Unified validation workflow and gated automatic tags |
| #112, #64 | `f5a8a0e` | Reviewed and closed **not planned**; no decorator/database implementation |

Per-issue specifications, decisions and acceptance evidence are linked from
[the current backlog](../NEXT.md#platform-cleanup-loop).

## Final checks

- Workspace `make lint docs-check test`: passed; 2,251 pytest passes, 75 optional/live
  skips across 20 suites, plus five release-tool unit tests.
- NCBI and AGORA strict conformance/golden gates: passed.
- All 17 marked capability inventories match their specs; 58 exact reference rows match
  runtime declarations and 67 documented commands parse against the current CLI.
- All GitHub workflows pass isolated actionlint 1.7.12 validation.
- Built wheels and source distributions for core 0.22.2, toolkit 0.6.22, NCBI 0.2.14
  and AGORA 0.2.11. New modules are present in the wheels. A fresh isolated wheel install
  imported the public additions and loaded AGORA membership successfully.
- Documentation links/anchors and `git diff --check`: passed.

The temporary wheel-install environment was removed. Small build artifacts and diagnostic
logs remain ignored under `.audit-local` or `/tmp`; no global tool install or source-data
acquisition occurred. No API backend fetch implementation changed, so live provider E2E
was not required or run for this loop.

Hosted CI/CodeQL has not been exercised by a PR/main run. Local workflow checks cannot
prove GitHub permissions or runner behavior. Tag creation is still automatic only after
an authorized main push; no manual tags or publishing dispatches were made.

## Remaining work

Only the deliberately deferred issues remain open: publication #142, further durable
cache/resume #143 and GTDB cross-tree semantics #234. Parent trackers #165 and #147 stay
open for that GTDB finding. Final researcher examples and joint reader testing remain
deferred until the platform direction is settled.
