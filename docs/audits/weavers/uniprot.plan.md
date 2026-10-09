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

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #183, #184. Search pages and projected nested fields are validated. Search HTTP 400/404 is a miss; mapping-job HTTP 400/404 remains a job failure. Submission, polling and result envelopes must contain meaningful job/result evidence and correlated input identifiers. A failed into-hub source-database job group preserves other groups. Mapping pagination repeats/excessive pages fail rather than looping forever. Broader mapping ordering/configuration/polling-budget work remains separately tracked.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.

## Shared coverage work implemented

The #151 findings are implemented and verified in
[SH-04 implementation and migration evidence](SH-04.implementation.md).
Other work packages in this source plan remain separately tracked.

## SH-08 identity implementation

Primary shared identity findings are implemented under #155; see
[SH-08 implementation and validation](SH-08.implementation.md). Source-specific
work packages with additional feature proposals remain tracked by their own groups.

Shared documentation findings in #148 are implemented; see
[SH-01 evidence and scope](SH-01.implementation.md). Other source capability and
configuration work remains owned by its existing issues.

Shared configuration/lifecycle findings in #149 are implemented; see
[SH-02 acceptance, verification and migrations](SH-02.implementation.md).
Source-specific remaining proposals and capabilities stay separately tracked.

## Source-group implementation progress

WP-UNIPROT-03 and remaining adverse verification for requirement 010 are implemented
under #186/#189; see [source evidence and design](SRC-UNIPROT.implementation.md).
The composed private job adapter preserves public capabilities and source-local
selection. WP-UNIPROT-06/#188 remains pending a feature scope decision; sequence,
annotation evidence and proteome enumeration have not been added by this refactor.
