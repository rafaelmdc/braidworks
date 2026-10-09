# FAPROTAX source audit implementation

Issues #256, #257, #258, #259; version 0.1.4. Local branch `fix/source-audit-pack-10`.

A private pure parser creates immutable ordered rules with group attributes and original literature comments. The interpreter implements provider-default complete-word matching over full lineage text, honoring alphanumeric/hyphen boundaries and case-insensitive word order. Full NCBI binomials therefore match species epithets without suffix or hyphen-word false positives.

Add/subtract/intersect operations evaluate membership in source order, including members after exclusions; operations are not mistaken for group names. Quoted members work. Missing references, cycles, forward references and malformed definitions are actionable errors; runtime bundled-source errors become error records. Batch-local duplicate sharing, worker-thread execution and detached result lists remain intact.

Dedicated tests cover real Methanosarcina barkeri, chloroplast exclusions, word boundaries, operations, quotes, metadata, references/cycles and error records. The provider's unmodified 1.2.12 database and its notice remain verbatim. Documentation distinguishes putative taxonomic affiliation from measured function, and NO_MATCH from demonstrated absence.

A differential run against provider collapse_table.py 1.3.7 compared **25,068 cases across all 92 groups with zero mismatches**, including every bundled member pattern, simulated binomials, suffix controls and biological examples. Provider code was downloaded only into ignored audit storage; no new dependencies installed. The retained reproduction script evaluates selected reference functions without running its CLI or importing scientific dependencies. This verifies parser/matcher semantics, not the biological correctness of every annotation.

Optional public explanations/literature output is split into #297 for user scope review; parsed evidence is retained privately and no public output has been added.

## Verification

Package suite: **31 passed, no skips**. Strict verification passed. Repository lint passed. Full workspace result is recorded in the batch report after completion.

Repository validation: `make test` passed (2094 pytest tests, 56 opt-in skips, plus 5 tool unittest checks); `make lint` passed. Tooling used the isolated audit environment.
