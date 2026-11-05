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

## A row and its status

A result has one row per input, in the order you gave them; duplicate inputs stay
separate rows. A row's `status` summarizes the whole route for that input, while
`missing` names each requested field it lacks. The two answer different questions.
A `resolved` row produced at least one requested field. An `unresolved` row means no
attempted route produced any, which is a statement about those lookups, not about
biology. `review` means a match is waiting for your decision, and `error` means a
technical failure blocked the row. A source that fails on one branch does not
discard what another branch found: the row can be `resolved` with a field in
`missing` and a diagnostic in `result.errors`.

## What a list's size tells you

Fields that hold several values (GO terms, structures, interaction partners) come
back whole, and each list carries its size. `complete` means the source returned
everything it has for that lookup. When a source has to stop early, for example at
a page limit or a partner cap, the list says so. It shows `25 of 321` when the source
reported its true total, and `25+` when it could not. A list is never silently cut
for display. Long lists are only shortened on screen.

A complete list is complete *for that source and lookup*: 131 GO terms means QuickGO
returned 131 distinct terms for that accession under the filters used. It is not a
claim about every annotation that exists, nor a measure of biological importance.
Counts of other things, such as experiments behind a disease association, use their
own names (`experiment_count`) and are not a list's size.

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

For practical coverage checks and export steps, use [the result guide](../how-to/check-results.md).
Exact shapes are in [result reference](../reference/results.md); storage controls are
in [cache and saved runs](../how-to/cache-and-resume.md).
