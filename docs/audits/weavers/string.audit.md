# STRING weaver audit

Date: 2026-10-08; revision `d5e7543`; version `0.1.6`, core floor `0.13.0`.
Status audited locally; proposals not implemented.

| ID | Priority/confidence | Finding/evidence | Recommendation |
|---|---|---|---|
| WV-STRING-001 | P1 verified | Fan-out carries only partner display names; distinct STRING IDs with same name collapse, taxon lost, downstream UniProt representative search can change species | Stable partner identity/taxon bridge; names remain descriptive; explicit mapping instead of ambiguous re-search |
| WV-STRING-002 | P1 verified | Upstream limit25 restricts fetched neighbors; fan set is restricted, count is returned rows, docs describe a display cap/all partners | Honest scope/completeness metadata; define bounded versus full set semantics before claiming full fan |
| WV-STRING-003 | P1 verified | Duplicate edges inflate count; equal score/name IDs retain response order | Dedup by stable source/target identity and deterministic ID tie-break |
| WV-STRING-004 | P1 verified | Static `string-db-v12` identity with mutable default service now reporting12.5; limit/endpoint omitted | Pin supported version or report actual version/config identity; do not label live data v12 without agreement |
| WV-STRING-005 | P2 verified/researched | No score/network_type/species declared parameters; docs imply interactions without explaining functional association versus binding | Explicit functional/physical semantics and supported filters with documented defaults |
| WV-STRING-006 | P2 verified | JSON decoding/list member shape unvalidated; wrong object returns empty; bad echoes silently omitted; all job groups fail together | Validated mapping/edge correlation and affected-group error boundaries |
| WV-STRING-007 | P2 verified | Builder/lifecycle and stale force/no-bulk docs repeat shared gaps; optional echo contract not requested | Config/lifecycle shared policy; request echo explicitly or support queryIndex safely; bounded POST where appropriate |

## Research and coverage

Sources accessed2026-10-08: [official API](https://string-db.org/help/api/),
[score interpretation](https://string-db.org/help/scores/),
[provider scientific use examples](https://en.string-db.org/cgi/info),
[training enrichment exercise](https://string-db.org/string_course/exercise_2_explore_the_new_enrichment_functionality.pdf).
The API explicitly describes identifier mapping followed by network/enrichment as
a common workflow. This provider statement is stronger than guessing from endpoint
availability, but does not quantify relative frequency.

| Workflow | Support | Gap |
|---|---|---|
| Explore scored neighbors for a protein | Partial: two-step ID resolution and partner fetch | Stable identity/species, score/network selection and bounded result scope |
| Retrieve interactions among a supplied protein set | Absent as dataset network | Partner lists are not induced-network analysis; conditional separate capability |
| Functional or interaction enrichment of a protein set | Absent | Statistical/background-aware cohort contract needed; defer |
| Distinguish functional associations from physical contacts | Partial channel scores | Network-type controls and accurate scientific documentation |

API advises version-specific production URL, POST for longer queries and one second
between calls. Pacing machinery exists, but a backend advertising support does not
automatically configure a provider-safe default. Network requests above10 proteins
may require species per documentation; mixed-species bulk assumptions need a bounded
live test before promising them. That case was not probed in this audit.

## Capabilities and full checklist

`list_interactions`, API-only accession input, maxbatch25; summary/full groups emit
name fan set, names/count and edge records with partner STRING ID and channel scores.
No declared query parameters or local database/build.

- **Correctness:** scores mean confidence in association, not binding strength.
  Return scope and ID/taxon loss are more important than adding pattern classes.
  Zero subscores dropped from channel dict; document absent versus zero distinction.
- **Architecture:** thin shared dispatch retained. `_edge`/`_extract` provide functional
  core but should project stable identity, dedup and sort. Small ID-resolution and
  network endpoint adapters clarify contracts; no class per evidence channel.
- **Transport:** grouped two bulk GET steps; chunks100 though normalbatch25, pacing
  present; no API retries/client closing. `_string_ids` keeps first response mapping,
  silently ignores absent echoes; correlation must not turn malformed data into absence.
- **Build/parity/provenance:** no local build, only live source; version pinning and
  effective thresholds belong in identity. Source license/citation provided.
- **Connectivity/usability:** current name bridge is reachable but biologically weak;
  prefer registered stable STRING key plus verified downstream mapping. Existing name
  output needs compatibility treatment, not silent replacement. CLI/Python examples
  lack knobs/execution detail; stale no-bulk spec comment contradicts code.
- **Tests:** two-call batching covered only human-shaped fixtures; duplicates, equal
  names/different IDs, >10/species, cap scope and version drift absent. Two live tests
  assert TP53/MDM2 structure; not downstream identity or exhaustive coverage.

## Evidence

**28 passed, 2 skipped**; strict fixture gate passed. Pure three-edge probe with two
stable IDs and one duplicate returns count3/names3 but name fan length1.
Small live `get_string_ids` GETs for P04637/P69905 returned200 with human STRING IDs,
both with and without echo_query=1. Therefore missing explicit echo is a contract
robustness gap, not a currently observed failure: JSON currently includes queryItem.
Version endpoint returned12.5/stable address version-12-5. No full live suite/network
or enrichment run performed. No claim that mixed-species batches currently fail.

[Backend](../../../weavers/string_weaver/src/string_weaver/backends/api.py),
[spec](../../../weavers/string_weaver/weaver.spec.toml),
[tests](../../../weavers/string_weaver/tests/test_api.py),
[docs](../../../weavers/string_weaver/README.md).
[Spec](string.spec.md), [plan](string.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.
