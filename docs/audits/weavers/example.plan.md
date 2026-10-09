# Example proposed implementation plan

Status: proposed. [Spec](example.spec.md); [audit](example.audit.md).
Finding issues are now tracked under #147; optional proposals remain scope decisions.

| Package | Requirements | Work and validation |
|---|---|---|
| WP-EXAMPLE-01 | 001, 003 | Correct safe regeneration instructions, explain scaffold deviations/CSV mapping/fingerprint rules and run a complete offline usage example. Documentation-only commit. |
| WP-EXAMPLE-02 | 002 | Validate builder configuration without new abstractions; prove empty config and provider compatibility plus clear typo rejection. Runtime patch bump. |
| WP-EXAMPLE-03 | 004 | Replace fabricated order samples with all five real taxids; add focused miss/duplicate/output-selection assertions where existing contracts do not cover them. Preserve contract definitions. |
| WP-EXAMPLE-04 | 005 | Update source metadata in spec, generate into scratch, selectively apply generated vocab/version changes. Confirm backend stays intact. |
| WP-EXAMPLE-05 | 006, optional | Decide whether pure parsing improves the teaching reference; if accepted extract parser and specify malformed data behavior. Avoid repository/strategy classes. |

Order: 01 first because current instructions risk overwrites; 02–04 can follow in
small commits. Consolidate necessary package bump consistently across spec, metadata
and generated vocab, update lockfile as needed. Do not bump per docs-only edit.

Acceptance: package Make tests, strict verification, affected lint, executable README
example and spec/vocab agreement. Check installed CSV only if packaging/resources
change. No live E2E necessary: there is no API backend. Record local commit hashes
and outcomes on accepted implementation issues; do not push or close delivery trackers.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.

Shared documentation findings in #148 are implemented; see
[SH-01 evidence and scope](SH-01.implementation.md). Other source capability and
configuration work remains owned by its existing issues.

Shared configuration/lifecycle findings in #149 are implemented; see
[SH-02 acceptance, verification and migrations](SH-02.implementation.md).
Source-specific remaining proposals and capabilities stay separately tracked.
