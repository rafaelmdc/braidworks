# Combined implementation plan

Date: 2026-10-05. Status: W01–W07 and W09–W12 verified locally; W08 discovery verified/retry planned, W14 planned, W13 conditional.
[Programme index](README.md). Matching detailed plans: [readiness](readiness.plan.md),
[persistence](persistence.plan.md), [application](application.plan.md). Branch: `refactor/persistence-foundations`.
No push/merge/publication is part of this programme. Round 1 is the existing local
baseline, not another rewrite to perform.

## Ordered work packages

| Step | Requirements | Concrete work / reviewable result | Depends on | Status |
|---|---|---|---|---|
| W00 | RD01–08 | Record current baseline and keep regression contracts | Existing readiness commits | Baseline recorded |
| W01 | PF01 | SQLite ownership helpers; NCBI explicit handles and schema initialization | W00 | Verified locally; see persistence.plan.md |
| W02 | PF02 | Safe build-lock ownership and source identity/session checks | W01 | Verified locally; see persistence.plan.md |
| W03 | PF03 | Separate review repository/history migration; batch thread boundaries | W01–02 | Verified locally; see persistence.plan.md |
| W04 | AP01–02 | QueryRequest/Options/PreparedQuery; shared prepare/execute service | W00; coordinate W03 APIs | Verified locally; see application.plan.md |
| W05 | AP03 | Prepared-plan graph/code renderers; CLI/Python artifact equivalence | W04 | Verified locally; see application.plan.md |
| W06 | AP04–05 | Shared GET/POST stream lifecycle; canonical browser request encoder | W04–05 | Verified locally; see application.plan.md |
| W07 | AP06 | Pure scaffold generation/validation and safe writes | W00; align new runtime floor | Verified locally; see scaffold.plan.md |
| W08 | AP07 | Structured discovery and explicit worker retry decisions | W00 | A07a verified locally; A07b planned |
| W09 | PF04 | Versioned cache codec/policy and SQLite cache adapter | W01–04 | Verified locally; see persistence.plan.md |
| W10 | PF05 | Stable execution identities/state and in-memory continuation equivalence | W04; preserve W06 events | Verified locally; see persistence.plan.md |
| W11 | PF06 | Transactional RunStore/checkpoint ownership/recovery | W01, W02, W10 | Verified locally; see persistence.plan.md |
| W12 | PF07 | Cache/run status/resume across CLI/API/browser and human docs | W05–06, W09–11 | Verified locally; see persistence.plan.md |
| W13 | AP08 | NCBI dispatch fit assessment; adapter only if justified | W03–04, W08 | Conditional |
| W14 | RD01–08 plus all PF/AP | Full integrated validation, migrations, artifacts and user workflows | Required work complete | Planned |

Execute sequentially in this checkout. Independent rows describe dependency flexibility,
not authorization to spawn agents or create parallel edits. A work package may need
several small commits; the table does not prescribe one oversized commit per row.

## Entry and completion gates

Before changing a boundary, inspect its actual callers and existing tests. Reproduce
consequential defects with tiny data; preserve the existing regression when extracting
code. Write contract tests for real adapter/state boundaries, not tests mirroring a
function line by line. For each work package record:

- requirement IDs, changed public/implementation boundaries and compatibility choices;
- targeted checks and their actual results;
- migrations/behavior changes and material limitations;
- local commit hashes and remaining acceptance cases.

Do not mark a work package complete until its requirement's acceptance checks pass.
Do not close remote delivery issues merely because code is committed locally. Existing
issues #136–141 remain delivery trackers; #144/#145 own new refactors; #143 owns cache
and resume acceptance. Record conditional AP08 as implemented or rejected with evidence.

## Decisions specified for the first implementation

- Keep stdlib SQLite. No ORM, DI container, event broker, new database service or
  required frontend toolchain. Protocols/functions/value objects are sufficient.
- Source readers bind to a generation. Detect replacement and require reopening;
  never transparently change identity beneath a cached result.
- Separate user-reviewed decisions from reference artifacts with an idempotent migration.
- Keep memory cache as default. Opt-in persistence starts with configurable positive
  TTL 1 hour, negative TTL 5 minutes and 256 MiB payload budget. These are chosen
  operational defaults, not a promise of upstream freshness or exact on-disk size.
- Checkpoint fully applied waves/traversal phases. A crash within a wave may repeat
  source reads. Preserve exactly-once run-state advancement through revisions/claims.
- Use one query service/executor for all interfaces. Retain fetch's unique-ID facade
  behavior and direct-capability semantics as explicit adapters, not accidental changes.
- Keep existing public wrappers and transport response fields initially. New contracts
  round-trip JSON; migrations/schema incompatibilities fail clearly.

Implementation details such as supported OS lock fallback, review migration deduplication
and snapshot size must be resolved by their work package's evidence before that commit.
They are engineering decisions, not reasons to invent broad extension frameworks.
If a material product tradeoff cannot be resolved from these contracts, bring the
concrete options/evidence to the user while progressing on independent authorized work.

## Integration ownership

Application service owns request preparation and grouping; executor owns actual wave
transitions; persistence owns storage. PreparedQuery can expose serializable plans and
options without serializing registry/runner handles. ExecutionState/checkpoint records
reuse those definitions. Avoid duplicate schemas for the same option set or competing
input/child identity generators.

Progress events remain compatible observations. Checkpoint publication is a distinct
post-application boundary. The stream adapter does not save checkpoints itself.
Archives remain independent observation exports, and reviewed decisions remain history.
No new feature may bypass review, expansion, request pacing or worker identity checks.

## Required verification

Targeted package tests after each consequential change. Run workspace `make lint` and
`make test` at coherent integration checkpoints, using the existing isolated environment.
Keep per-package cwd sensitivity. Use deterministic clock/crash/concurrency tests for
new persistent contracts; subprocess tests for real local lock ownership. Rehearse real
Firefox journeys after browser changes. Live E2E is mandatory for changed API behavior,
using API-only selections where local-data tests would download large artifacts.

At W14: strict weaver gates; current wheel/sdist contents and clean installs; declared
minimum-core fixture goldens; installed-wheel scaffold/API/browser smoke; strict Twine
metadata checks; document links and workflow lint. Update inventories where manifests
change. No remote CI/fleet/release certification unless actually exercised.

Independent versions must agree across affected specs/pyproject/generated vocab; raise
core floors for new dependencies. Preserve NCBI's handwritten-vocab exception. Never
stage `.audit-local`, databases, environments, downloads or archives. Publish no tags.
