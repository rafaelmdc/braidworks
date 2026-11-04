# NCBI source audit implementation

Issues #230; version 0.2.11. Local branch `fix/source-audit-pack-10`.

Public ncbi_weaver.intermediate LineageEntry, CandidateMatch and TaxonMatch now round-trip actual JSON, including nested lineage/candidates, every status, warnings and optional values. Reconstructed collections are detached.

The unused monolithic ABC becomes structural ResolutionBackend, plus separate TaxonomyChildrenBackend, GenomeBackend and GeneBackend protocols reflecting actual backend responsibilities. Taxonomy-only implementations do not inherit six unsupported defaults. Dispatch checks optional operations and raises structural UnsupportedCapability instead of AttributeError. No biology enters core and no Datasets HTTP/parsing code changes.

Migration: custom backends implement structural interfaces instead of inheriting default operation methods. Runtime duck-typed implementations continue to work; no new capability or backend support is promised. Tests cover all enum statuses, nested mutation isolation, structural Datasets conformance and missing optional operations. Additional extension docs/local descendant/merged-ID scope remains #231.

## Verification

Package suite: **222 passed, 13 opt-in skips**. Strict verification passed. Repository lint passed. Full workspace result is recorded in the batch report after completion.

Repository validation: `make test` passed (2094 pytest tests, 56 opt-in skips, plus 5 tool unittest checks); `make lint` passed. Tooling used the isolated audit environment.

## Approved local taxid history — #231

Version 0.2.12 adds local-only `ncbi.describe_taxon_history` through an optional
structural backend operation. Current name/taxid resolver behavior is unchanged.
The existing atomic dump builder parses optional merged/deleted files before
publication, rejecting duplicate/conflicting identities and cyclic merge graphs.
It persists history tables and availability metadata. Full archive hashes already
cover history content in source fingerprints; older DBs remain readable and
report unavailable history honestly. Deleted IDs never acquire an invented successor.

Verification: 228 package tests passed, 13 opt-in skips; seven targeted history
tests passed (including an additional atomic failed-rebuild test); strict passed.
No HTTP backend changed and no full source database was downloaded. Local
descendants remain deferred, so #231 stays open for that remaining scope.
