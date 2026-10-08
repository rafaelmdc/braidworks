# UniProt proposed implementation plan

Status: proposed. [Spec](uniprot.spec.md); [audit](uniprot.audit.md).

| Package | Requirements | Work/acceptance |
|---|---|---|
| WP-UNIPROT-01 | 001, 010 | Separate explicit accession lookup from representative search; tests prove exact unreviewed identity and absence/species behavior. Run affected live known-truth tests. |
| WP-UNIPROT-02 | 002, 003, 010 | Define target-specific groups and count/record semantics before code; normalize distinct ordered mappings; shared executor and durable-cache request-order regressions. Apply spec/generated vocab selectively. |
| WP-UNIPROT-03 | 004, 005, 007, 010 | Extract small source-local mapping-job adapter and pure page normalization; validate schema, bound pagination/polling and isolate failures. Add adverse response/job/cancellation cases. |
| WP-UNIPROT-04 | 006 | Expose explicit backend configuration and lifecycle ownership; verify provider forwarding, typo errors and source identities. Coordinate any common lifecycle proposal with synthesis. |
| WP-UNIPROT-05 | 008 | Correct canonical/isoform promises, contributor capability list and regeneration guidance; demonstrate mapping and configured Python usage. |
| WP-UNIPROT-06 | 009, conditional | After feature scope review, specify describe_protein accession input, sequence/evidence groups and costs. Add real samples/goldens, implement and verify connectivity/live outputs. |

Implement 01–02 first because incorrect identities/cache coverage affect results.
03 may then reorganize transport around established behavior, without combining a
large refactor with unspecified output changes. 04–05 follow; 06 needs a separate
feature decision. Do not block correctness on optional proteomics expansion.

Before coding accepted packages, create linked actionable issues. Keep each change
reviewable, preserve conformance/contract checks, patch versions consistently and
raise core floor only for new imports. Run affected Make tests, strict verification
and lint; run live E2E after every API backend change as AGENTS requires. Record
credentials/network limitations honestly. Regenerate catalogs after manifest changes.
Broader artifact/minimum-floor checks apply if shared APIs/packaging change and at
final acceptance. Local commits only; no push, tags or publication.
