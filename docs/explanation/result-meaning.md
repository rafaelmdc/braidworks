# What a lookup result establishes

Braidworks connects source observations. Whether those observations answer your
scientific question depends on coverage, identity and the source's measurement or
inference rules. A successful route is only part of that assessment.

## Coverage and review


| Outcome | What to do |
|---|---|
| Resolved | Use the returned values and check `missing` for requested fields that were not produced. |
| Unresolved | Keep the input in your coverage report; the source found no match along the attempted route. |
| Review | Inspect the candidates or review flag before using an uncertain match. |
| Error | Read the diagnostic. A technical failure does not establish biological absence. |

Resolved means **at least one** target was produced. It does not mean every requested
field is present. A no-match likewise does not prove that an organism lacks a trait
or that a protein has no biological role; it describes the source lookup.

Ambiguous resolver matches pause by default. Expansion controls how many related
entities to follow; it does not authorize choosing an ambiguous match. Some lookup
capabilities select a representative instead of emitting candidates. In particular,
UniProt gene-symbol search returns one representative: specify the organism and use
an accession when you need an exact protein.

## Related entities and original inputs

Expansion can turn one original input into several terminal children. Their count
describes the expanded result, not the number of original samples or proteins. Use
source-row and parent relationships to keep those levels separate in an analysis.
An ordered representative is a source-selection rule, not a ranking of scientific
suitability for your study.

## Saved observations and reproducibility

An archive records what happened during a run. Source identities and timestamps help
you inspect that observation, but a live API may change without a new contract
fingerprint. A cache reuses observations; a saved run records progress. Neither freezes
a provider database. Keep these distinctions when reporting an analysis.

For practical coverage checks and export steps, use [the result guide](../results.md).
Exact shapes are in [result reference](../reference/results.md); storage controls are
in [cache and saved runs](../persistence.md).
