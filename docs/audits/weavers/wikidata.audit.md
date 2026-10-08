# Wikidata weaver audit

Date: 2026-10-08; revision `d5e7543`; package 0.1.5/core floor 0.13.0.
Status audited locally; no production edits.

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-WIKIDATA-001 | P1 reproduced/code | Valid JSON wrong shape {} becomes NO_MATCH; array/null binding escapes AttributeError outside retry boundary; malformed JSON retries already implemented | Validate SPARQL result/binding shape before accumulation and preserve per-chunk failure values |
| WV-WIKIDATA-002 | P2 reproduced/code | Literal escaping omits control/newline characters; generated query400 treated NO_MATCH by generic not-found helper | Complete SPARQL literal serialization/input validation; query syntax/config errors ERROR, not absent taxon |
| WV-WIKIDATA-003 | P2 code | Vernacular list follows binding order; first rank/title/sitelink wins conflicting duplicate bindings | Pure stable dedup/projection and explicit conflict diagnostics/tiebreak |
| WV-WIKIDATA-004 | P2 verified/code | Config ignored, owned client unclosed, endpoint absent from monthly fingerprint; UA still Cladewright identity | Shared owner WV-UNIPROT-006; configurable truthful service identity/lifecycle |
| WV-WIKIDATA-005 | P2 verified | Scientific-name only, no stable NCBI ID/QID input or QID describe; taxon rank only hidden disambiguator; English output fixed | Conditional stable-ID map/describe and language parameter with coherent title/project provenance |
| WV-WIKIDATA-006 | P2 code | Retry policy ignores Retry-After/elapsed budget and erases final reason; rank filter only disambiguates multi-hit, single wrong rank still resolved | Endpoint policy/budget/error detail; document expected_rank as disambiguator or specify stricter filter separately |
| WV-WIKIDATA-007 | P2 verified | Contributor current outputs omit sitelinks, expansion TODO and force overwrite guidance; source sample lacks echoed sname | Accurate usage/source samples/extension docs; shared owner WV-EXAMPLE-001 |

Do not flag current backend as serial one-request-per-name: it correctly deduplicates
and POSTs VALUES chunks200, preserving partial chunk errors and sorted QID candidates.
expected_rank behavior is documented as disambiguation, so single-hit mismatch is a
usability policy question, not necessarily a contract violation.

## Research/workflow coverage

Primary accessed2026-10-08:
[Taxonomy project](https://www.wikidata.org/wiki/Wikidata:WikiProject_Taxonomy/en),
[query help](https://www.wikidata.org/wiki/Help:Queries),
[query-service manual](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual),
[biology glossary](https://commons.wikimedia.org/wiki/Help:Biology_wikidata_glossary/Wikidata_Taxon_Item).
Indexed primary text describes P225 names, P105 ranks, P171 parents and P685 NCBI IDs,
plus name duplicate reports. No popular-workflow count asserted.

| Workflow | Coverage | Gap/decision |
|---|---|---|
| Link scientific taxon names to Wikidata/Wikipedia | Bulk resolver, ambiguity review, English title | Stable IDs and explicit taxonomic context useful for cross-code homonyms |
| Enrich labels/vernacular aliases across projects/languages | English names and sitelink count | Optional language, statement/source semantics and exact identity |
| Traverse parent taxa/crosslink biological databases | QID output only | Conditional QID describe/P685 map/P171 relations; don't mirror all Wikidata properties |
| Rank public attention through encyclopedia signals | Sitelinks + downstream pageviews | Language reach proxy, not scientific importance; preserve project/source period |

## Complete checklist

- **Capabilities:** one max-default resolver, core always computed, names group and
  declared expected_rank. Scientific-name consumer joins existing sources; QID/title
  useful outputs, title chains Wikipedia. Current taxon restriction appropriately narrow.
- **OOP/functional:** shared resolver dispatch and pure accumulation helpers adequate.
  Composed SPARQL request adapter/validated binding projection fits retries and new
  optional ID entry; no class per property or generic graph database framework.
- **Batch/errors:** whole VALUES POST chunking avoids URL limits; duplicate names reused,
  chunk errors scoped. Existing retry malformed JSON good; structure check and error reason
  missing. Pacing wrapper retained; no new live WDQS request needed for code findings.
- **Groups/params/cache:** all fields queried even requested small slice; avoid excessive
  optional joins if measured, preserving always-computed core. Monthly fingerprint is
  freshness policy, not revision snapshot. Params core-validated and effective cache-keyed.
- **Build/parity/provenance:** API only, fixture MockTransport; no local build. Exact P225
  lookup can return duplicates; direct truthy properties omit richer statements/references,
  acceptable if scope clear. Project/language changes need semantic identity/default policy.
- **Docs/tests:** 26 passed,1 skipped and strict passed. Homonym/rank/retry/chunk-failure
  coverage strong; add malformed shape,400/control literal, shuffled aliases/conflicts and
  batch request-count checks. Python construction-only docs; safe contributor guidance.
  Source/software license metadata present, all version sites reviewed.

Offline `.audit-local/wiki-audit-probe.py` verifies malformed shapes/miss/escapes and raw
newline literal; no full live suite. [Backend](../../../weavers/wikidata_weaver/src/wikidata_weaver/backends/api.py),
[spec](../../../weavers/wikidata_weaver/weaver.spec.toml),
[tests](../../../weavers/wikidata_weaver/tests/test_api.py).
[Proposed spec](wikidata.spec.md), [plan](wikidata.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.

[Retained offline reproduction](../reproductions/weaver_wiki_sources.py) runs without network;
all database writes stay in temporary directories.
