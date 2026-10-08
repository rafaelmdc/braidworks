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
