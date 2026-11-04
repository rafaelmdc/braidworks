# UniProt #188 — implementation plan

1. Add capability/output groups and real source excerpt to the existing spec;
   register the two leaf output names. Use scratch generation and copy only vocab.
2. Add a source-local module with pure description normalization and bounded bulk
   acquisition. Compose it from the existing API backend and paced client; leave
   representative search and mapping-job semantics intact.
3. Add deterministic observed minimal fixture payloads and description goldens.
   Test group projections, preserved evidence, exact identities, sparse entries,
   duplicates, chunk calls/order, failures and pagination. Add meaningful live tests.
4. Document costs, primary/isoform scope and complete Python/CLI usage. Patch all
   package version sites, update lockfile, regenerate indexes/network view.
5. Run package tests, strict gate, live E2E and workspace lint/tests. Commit locally,
   record acceptance, close #188 and parent #158. No proteome enumeration or publish.

All five steps are implemented and verified; see [final acceptance evidence](SRC-UNIPROT.implementation.md).
