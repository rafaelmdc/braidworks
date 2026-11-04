# UniProt #188 — accepted exact-accession description

The user accepted the recommended long-term scope: exact primary-accession
`describe_protein`, with separate identity, sequence and annotation groups.
Proteome enumeration and isoform-specific retrieval are independent later work.

| Boundary | Accepted contract |
|---|---|
| Input | Existing shared `protein.uniprot.accession`; case-insensitive canonical primary accession syntax. No fuzzy search, organism substitution or secondary/isoform-to-primary fallback. |
| Identity (always) | Existing accession/name/gene/organism/reviewed/taxid/function/length outputs, retaining current display-summary semantics. |
| Sequence | New leaf `protein.sequence`, the canonical entry amino-acid string, not an isoform enumeration or inferred consensus. |
| Annotations | New leaf `protein.annotation.records`, structured comments/features/references with their original nested evidence, entryAudit/proteinExistence where available, and observed release headers. No evidence stripping in these records. |
| Cost | Identity uses compact fields; sequence adds sequence projection; annotations request the full JSON entry. The full response may contain sequence bytes, but sequence output is only projected when requested. No hidden annotation truncation. |
| Batching | Distinct valid accessions, sorted chunks of 25; bulk OR accession search, size 500; finite 10-page guard and repeated/malformed-link rejection. Results remapped by exact primary accession to original positions with detached projections. |
| Failures | Search 400/404 is NO_MATCH; expected HTTP/JSON/schema failures affect their chunk. Never emit partial successful data after a failed page. Cancellation/programming faults propagate. |
| Missing fields | Valid empty annotation categories are empty lists; optional identity fields omitted. A requested missing/invalid canonical sequence is an error for that entry, not a fabricated sequence. |
| Verification | Real current source sample, offline fixture/goldens, bulk count, duplicate/order, sparse/unreviewed, exact identity, error isolation, group costs, pagination and live cases. Contract tests unchanged. |

Observed source: bulk GET `/uniprotkb/search` on 2026-10-09 with P04637 and
A0A087WT22; observed release 2026_03. Sequence projection preserves sequence.value;
full entries preserve evidence-bearing comments/features/references. Provider
background: https://pmc.ncbi.nlm.nih.gov/articles/PMC12230682/ .
