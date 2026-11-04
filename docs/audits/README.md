# Current audit completion record — 2026-10-05

> **Historical programme record.** The implementation described here was pushed
> on 2026-10-10 and completed trackers were closed. Original checkpoints below
> retain their dates. Later cache/resume interfaces are documented in
> [cache and saved runs](../persistence.md); current source delivery is recorded in
> [weaver completion](../audits/weavers/remaining-features.plan.md).

Branch: `feat/publication-readiness`. Implementation is complete locally; remote delivery
is pending. Publishing and durable cache/resume are deferred at the user's request.

| Audit | Fixed | Deferred |
|---|---:|---:|
| Architecture | 10 | 0 |
| Repo health | 4 | 1 |
| CLI/API | 8 | 0 |
| Features | 6 | 1 |
| Documentation | 6 | 0 |
| Usability | 9 | 0 |
| Total | 43 | 2 |

These are 42 distinct fixes: A04-01 duplicates A03-05. Specs preserve original audit
observations as historical evidence; plans record remediation and earlier intermediate
checks. This completion record supersedes earlier pending-validation counts.

Validation: 1239 pytest tests and five release-tool tests pass, with 48 opt-in skips.
Core 399, toolkit 221, arq 51. Official Ruff lint passes. All 20 wheel/sdist pairs
build and pass artifact/content/clean-install checks and strict Twine checks. All 17
weavers' fixture goldens pass against their declared minimum core versions. Eleven
changed API families were tested against live sources; GTDB used only its API test,
and NCBI excluded heavyweight local-database tests. Firefox verified pasted duplicate
rows, recipe roundtrip, heterogeneous CSV upload, cancellation/task cleanup and retry.
Local documentation links and pinned workflow lint pass.

Distributed request accounting has mocked-transport and executable Redis Lua tests;
this does not certify a deployed Redis fleet. Publishing remains inactive. Archives
preserve observations, not frozen datasets or cross-process resume checkpoints.

The isolated tools, environments, logs and build artifacts remain under `.audit-local/`
and are excluded from commits. No system packages were installed.

## GitHub tracking

| Audit | Issue |
|---|---|
| Architecture and request pacing | [#136](https://github.com/rafaelmdc/braidworks/issues/136) |
| Repo health | [#137](https://github.com/rafaelmdc/braidworks/issues/137) |
| CLI/API | [#138](https://github.com/rafaelmdc/braidworks/issues/138) |
| Features | [#139](https://github.com/rafaelmdc/braidworks/issues/139) |
| Documentation | [#140](https://github.com/rafaelmdc/braidworks/issues/140) |
| Browser usability and batches | [#141](https://github.com/rafaelmdc/braidworks/issues/141) |
| Deferred publication | [#142](https://github.com/rafaelmdc/braidworks/issues/142) |
| Deferred cache/resume | [#143](https://github.com/rafaelmdc/braidworks/issues/143) |

Audit issues remain open until remote delivery and review; local implementation is complete.
