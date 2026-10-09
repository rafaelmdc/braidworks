# AlphaFold proposed implementation plan

Status proposed. [Spec](alphafold.spec.md).

| Package | Requirements | Work |
|---|---|---|
| WP-ALPHAFOLD-01 | 001, 005 | Define representative coverage semantics; retain source ranges; long-fragment/isoform fixtures and accurate docs. |
| WP-ALPHAFOLD-02 | 002 | Validate responses and isolate expected data failures; blank/null inputs, malformed list/member and unrelated successes. |
| WP-ALPHAFOLD-03 | 004 | Configured composition/lifecycle and endpoint identity, coordinated with shared synthesis. |
| WP-ALPHAFOLD-04 | 003, 006, conditional | Scope optional raw confidence references and complete model list/entry drill-down. Spec real samples/groups/keys first; avoid unnecessary strategy classes. |

01–02 before feature growth. Accepted implementation issues precede coding.
Package tests, strict verification, lint and live E2E for API changes; known-truth
canonical, isoform and fragment samples where available. Patch all version sites and
catalogs when needed. No downloads of full proteomes, pushes or publication.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #198. Prediction responses must be lists of model objects with an entry identifier and correctly typed projected fields. An empty list remains a miss. A malformed response affects only its accession; null/blank inputs do not issue requests.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.
