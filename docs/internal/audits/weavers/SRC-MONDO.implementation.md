# mondo source correctness implementation

Issue #277; package version 0.2.7. Implemented locally on `fix/source-audit-correctness-batch`.

Runtime ancestor traversal first retrieves a finite set of reachable identities with recursive UNION over IDs alone. A private helper rejects cycles and dangling parents, then computes shortest ancestor depths by breadth-first traversal. Invalid graph data becomes an error record, never an indefinite query or a confident partial match. Existing build-time DAG validation remains intact.

Regression tests mutate a valid database into a cycle or dangling graph, bound SQL execution to catch regressions, and assert explicit failure. Existing tests retain shortest-depth DAG results and one recursive query per distinct origin, with no ancestry query for identity-only requests.

## Verification

Package suite: **56 passed, 1 skipped**. Strict verification and repository checks are recorded with the issue closure. Other source findings remain open; this report closes only the issue named above.

Repository verification: `make lint` passed; `make test` passed (2045 pytest cases, 56 opt-in skips, plus the tool unittest suite). `weaverkit verify --strict` passed for this package. All tooling used the isolated audit environment.

## Approved direct identity, definition and history — #278

Version 0.2.8 adds direct `describe_disease` using the existing MONDO bridge.
OBO ingestion retains definitions and obsolete terms with separate replaced_by
and consider targets. Only current terms enter name/xref resolution indexes.
Requested history carries release/hash provenance and never follows a suggestion
as an identity replacement. Schema 4 explicitly requires rebuilding old DBs;
caller-supplied content hashes include the retained fields.

A bounded source prefix confirmed the real obsolete MONDO:0000002 stanza and
its replacement; that observed snippet is retained in the spec. Existing ambiguity
and predicate review remain unchanged. SSSOM mapping expansion stays deferred.

Verification: 57 package tests and strict passed. Tests cover current/obsolete/
consider/no-successor/unknown IDs, escaped definitions, source identity and
exclusion of obsolete terms from ordinary resolution. No HTTP backend changed
and no complete ontology was downloaded.
