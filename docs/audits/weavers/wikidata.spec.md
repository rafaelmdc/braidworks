# Wikidata proposed specification

Status proposed. [Evidence](wikidata.audit.md).

| Finding | Acceptance |
|---|---|
| WV-WIKIDATA-001 | Validated result shape and bindings; per-chunk ERROR retained for malformed source, no raw escapes/false NO_MATCH. |
| WV-WIKIDATA-002 | Literals encode supported controls safely; syntax400 distinguishes source/query error from empty valid results. |
| WV-WIKIDATA-003 | Alias/output correlation stable/deduplicated under shuffled bindings, conflict policy explicit. |
| WV-WIKIDATA-004 | Known config/source identity/lifecycle and truthful UA; monthly freshness documented. |
| WV-WIKIDATA-005 | Conditional stable-ID entry/QID describe/language parameter specified; project/title provenance coherent. |
| WV-WIKIDATA-006 | Retry limits/server advice/error detail/cancellation explicit; expected_rank documented disambiguator or deliberately reviewed stricter filter. |
| WV-WIKIDATA-007 | Accurate examples/outputs/echoed source sample and safe regeneration. |

Retain true resolver ambiguity, bulk POST and chunk isolation; do not rewrite lookup as
first-hit. Public shapes use existing JSON boundaries; register accepted bridges and patch
versions/floor. Local dumps/full graph mirror out of scope.
