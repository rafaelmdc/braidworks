# Wikipedia weaver audit

Date: 2026-10-08; revision `d5e7543`; package 0.1.3/core floor 0.13.3.
Status audited locally; proposals only.

| ID | Priority/confidence | Finding/evidence | Action |
|---|---|---|---|
| WV-WIKIPEDIA-001 | P1 verified/reproduced | Same pageviews output denotes API12-month all-agents sum vs local1-month user-only sum; result has no period/agent/project coverage | Explicit comparable measurement contract/source scope; backends must honor same requested window/agent or advertise different supported configuration |
| WV-WIKIPEDIA-002 | P1 reproduced | Monthly end inclusive: _window uses current month1 as endpoint; bounded live Jan→Mar request returns all three months. API sums every returned timestamp | Define twelve completed month interval correctly and validate returned bins/coverage |
| WV-WIKIPEDIA-003 | P1 reproduced | ensure requested February returns existing January DB because validity ignores requested stamp; year/month alone don't select local; prebuilt DB requires supplied month | Validate resource requested month and actual metadata; explicit source selection/config |
| WV-WIKIPEDIA-004 | P1 reproduced/code | {} success gives found=True/pageviews0; invalid JSON/views escape gather and can fail whole batch | Validated per-article schema/counts/status with partial sibling isolation; valid zero distinct from absent/malformed |
| WV-WIKIPEDIA-005 | P2 reproduced/code | Unbounded gather repeats duplicate titles; no owned-client close, ignored kwargs/static endpoint omission, old Cladewright UA | Shared lifecycle/config owner; bounded distinct-title fetch and source identity |
| WV-WIKIPEDIA-006 | P2 code | Dump parsing silently skips malformed rows, accepts negative counts; no source content checksum/build coverage, only month plus build_id | Source hash/parser coverage validation, explicit project/access/agent source descriptor |
| WV-WIKIPEDIA-007 | P2 verified | No temporal series/window/agent/project parameters; redirects/title normalization/coverage absent; contributor expansion TODO and unsafe force instructions | Scoped parameter/series proposal, honest title semantics/docs, shared safe-regeneration owner |

001 README already acknowledges period mismatch but not agent mismatch; documentation
alone cannot make two backends semantically interchangeable. Existing source-binding
identity includes local build_id; no claim all rebuilds same month collide. 002 proves
endpoint inclusivity on historical bins; current incomplete month availability can vary,
so validate response instead of assuming every live request returns13 bins.

## Research/workflow matrix

Primary accessed2026-10-08:
[Analytics API guide](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/getting-started.html),
[pageview concept](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/concepts/page-views.html),
[API reference](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html),
[public datasets](https://wikitech.wikimedia.org/wiki/Data_Platform/Discover_data).
Indexed official docs distinguish traffic agent/access/project and describe page metrics
comparison. Bounded actual per-article GET verified interval semantics independently.

| Workflow | Current support | Gap/decision |
|---|---|---|
| Compare article attention over a defined period | One scalar, differing backend scope | Explicit period/agent/project and comparable totals |
| Track trends/events and seasonal changes | Monthly bins discarded | Conditional monthly series output/window parameter |
| Rank many titles without per-title network calls | Streaming monthly dump→indexed local DB | Same defined metric across source modes, checksum/coverage and month validation |
| Compare languages or access modes | English all-access fixed | Conditional project/agent/access parameters; title tied to language/project |

Pageviews measure observed requests under Wikimedia definitions, not unique people,
scientific importance or biological traits. Redirect/moved article accounting must follow
provider semantics; don't invent automatic combined-page historical totals.

## Complete checklist

- **Capability/connectivity:** one lookup describe_pageviews, title input from Wikidata,
  one scalar output, API/local both declared. No parameters/groups beyond core and no
  fan. Domain-neutral measurement backend appropriate; no additional biology types needed.
- **OOP/functional:** shared runtime, source-local backend and SourceBinding good.
  Pure measurement-scope/window and validated bin reduction plus composed dump index
  acquisition provide useful design seams; no inheritance per time period/title/project.
  Public scope descriptors, if introduced, need JSON round trips.
- **Build:** genuine streamed bz2 ingestion/batched UPSERT sums access modes with
  bounded row buffer; generic consent/lock/headroom/atomic setup present. Temporary download
  cleanup implemented. Don't replace working streamer with in-memory whole dump. Validator
  checks month/populated table, not requested month/agent/source hash.
- **Batch/errors/order:** local batch off event loop/read session pinned, order retained;
  API per-title endpoint correctly concurrent but no dedup/bounds/sibling JSON isolation.
  Missing title currently stringifies None; normalize valid inputs consistently.
- **Groups/cache/provenance:** monthly freshness vs dump identity documented; no period
  field means scalar cannot be compared without out-of-band backend knowledge. Month-end
  race between fingerprint and execution scope possible, fix with one effective descriptor.
- **Docs/usability:** useful CLI/local constructor and transparent one-month caveat;
  missing agent difference/source coverage. No Python execution or source update checklist.
  Existing prebuilt custom-path requirement and silent requested-month reuse confusing.
- **Tests/releases:** 13 passed,1 skipped and strict passed. Local parsing/access summing/
  generation-change covered; no dedicated API shape/window/batch adverse suite. Add inclusive
  bins, agent/period parity, requested-month mismatch, duplicate titles and invalid numbers.
  No multi-GB dump downloaded or full live suite run in this audit.

`.audit-local/wiki-audit-probe.py`: wrong object→successful0, duplicate titles→two requests,
window20251001→20261001 and February reuse of January DB. Small historical live GET
`.../Brown_bear/monthly/2025010100/2025030100` returned200 and January/February/March.
[API](../../../weavers/wikipedia_weaver/src/wikipedia_weaver/backends/api.py),
[local](../../../weavers/wikipedia_weaver/src/wikipedia_weaver/backends/local.py),
[setup](../../../weavers/wikipedia_weaver/src/wikipedia_weaver/setup.py),
[factory](../../../weavers/wikipedia_weaver/src/wikipedia_weaver/factory.py).
[Proposed spec](wikipedia.spec.md), [plan](wikipedia.plan.md).

The [complete capability/interface/scaffold comparison](coverage.md) accounts for all
declared inputs/outputs/backends/parameters and common Python/CLI/browser limits.

[Retained offline reproduction](../reproductions/weaver_wiki_sources.py) runs without network;
all database writes stay in temporary directories.
