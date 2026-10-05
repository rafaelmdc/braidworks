# Round 1 plan: preserve and validate readiness

Spec: [readiness.spec.md](readiness.spec.md). Programme: [combined order](implementation.plan.md).
Status: fixes already implemented locally; this plan governs regression protection
through the new work and final integration W14. Do not reimplement completed fixes.
Tracking: #136–141 and [#146](https://github.com/rafaelmdc/braidworks/issues/146).

## Work packages

| Task | Requirement | When | Result / completion gate |
|---|---|---|---|
| R01 | RD01 | Before changing cache/executor/traversal, then W14 | Original correctness assertions preserved and relevant suites green |
| R02 | RD02 | Before changing query/transition policies, then W14 | Review, bounds, backend routing and references remain equivalent |
| R03 | RD03 | W04–06, W12 and W14 | CLI/API/browser parity and complete row accounting verified |
| R04 | RD04 | Affected source/archive work, then W14 | Source semantics, batching and archive outputs verified |
| R05 | RD05 | Worker/HTTP/query changes, then W14 | Request accounting and worker safety regressions pass |
| R06 | RD06 | Every public/package change, final W14 | Versions/floors/licenses/artifacts coherent |
| R07 | RD07 | Changed docs/manifests/interfaces, final W14 | Current commands, catalogs and local links checked |
| R08 | RD08 | Throughout | Publishing inactive; cache/resume follows its dedicated gates |

## R01 — Correctness regression inventory

Record existing cache coverage, seed restriction, batch cardinality and JSON error
classification tests from core `test_cache.py`, `test_runtime.py` and traversal suites.
Map each affected extraction to an existing assertion; add a regression only for a
new behavioral boundary or newly reproduced failure. Do not weaken tests to accommodate
moved code. Verify shared/defaulted parameter identity and nonfatal branch semantics
when query preparation or persisted codecs change.

Done when targeted tests pass with preserved assertion strength and the work-package
record links the relevant requirements/commits. Historical suite counts are not a gate.

## R02 — Review, expansion and routing invariants

Preserve ambiguous-candidate halt/explicit continuation, confidence floors, deterministic
selection and global expansion allocation. Test an oversized fan without allocating
unbounded children; exports must show explicit truncation. Preserve backend-policy
planning and alternate-route references. Exercise resumed equivalents when PF05–07 land.

Do not centralize these algorithms in a presenter or query adapter. Executor remains
the execution-policy owner. Gate applies after each affected state/query extraction.

## R03 — Human interface compatibility

Build a deterministic experiment matrix: homogeneous/heterogeneous inputs; duplicated
rows; shared values and row overrides; scoped/defaulted parameters; ordinary/traversed
runs; resolved/unresolved/review/error mixtures; expansion truncation. Compare terminal
data, identity and effective settings across CLI, API and browser, not identical envelope
formatting. Preserve fetch's documented unique-ID convenience behavior separately.

Execute generated commands/Python as part of AP03. Rehearse Firefox upload, recipe,
export, cancel/retry and keyboard focus after AP05/PF07. Keep old saved recipes and
GET streaming endpoint compatible unless a documented migration is deliberate.

## R04 — Source behavior and archives

Keep existing GO evidence/completeness and representative-selection fixtures. Verify
bulk endpoints remain bulk when dispatch/service layers move. Use request-count tests,
not timing alone, to distinguish batching from concurrent single-ID calls. Preserve
one output per input and deterministic ordering.

Check archives still capture initial inputs, effective settings, results and declared
source identities, remain atomic/no-overwrite and honestly describe remote mutability.
They are observation exports, not automatic checkpoints. Run live E2E for changed API
behavior; select API-only tests and do not acquire huge local reference data.

## R05 — Pacing and distributed safety

Retain redirect/page/poll charging, shared client hooks, cancellation-before-send,
process-wide local budget and task-local worker isolation. Preserve Redis capacity/rate
consistency and worker manifest/fingerprint checks. New durable cache must not bypass
arq's explicit homogeneity requirement. Inline/Lua tests are evidence of contracts,
not proof that a remote deployment is certified.

## R06 — Package integration

For each public change record affected independent packages, version bumps and raised
core floors. Update weaver spec/pyproject/generated vocab coherently; preserve NCBI's
handwritten exception. Regenerate only intended artifacts, never overwrite custom code
by globally scaffolding every package.

At W14 build all packages with `uv build --all-packages`, run the existing artifact
checker against current outputs, strict Twine metadata checks, declared-minimum-core
fixture runs and strict weaver gates. Rehearse installed-wheel code generation and
optional browser imports. Keep MIT software metadata and biological-source licenses
separate. No distribution file or environment is committed.

## R07 — Docs and catalogs

Update human commands at the same time as interface changes. Regenerate `make index`
and the network view when manifests change, using the isolated environment. Validate
local links, recipe examples and installed-package paths. State operational limits:
API data is not frozen, interrupted waves may repeat reads, thread cancellation is not
forced termination, and local SQLite is not a cross-host datastore.

## R08 — Delivery boundaries

Keep publication #142 deferred. No pushes, tags, merges, release jobs or account changes.
Cache/resume is allowed only in its ordered post-foundation work packages. Keep #136–141
open for remote delivery/review. Status records must separate local implementation,
local validation and remote acceptance.

## Verification, commits and exit

Use existing isolated tools and per-package cwd-sensitive test commands. Run relevant
Make targets for affected packages; workspace `make lint` and `make test` at coherent
integration checkpoints. Repeat/broaden checks only for changed code or unresolved
concerns. W14 includes package and browser integration checks after the final tree.

Record evidence in the active plan task/issue before each local implementation commit.
Commit docs/metadata changes with the behavior they explain where practical. Final
readiness record lists remaining limitations and exact local hashes; it does not claim
remote CI or publication. This plan completes at W14 when RD01–08 acceptance holds.
