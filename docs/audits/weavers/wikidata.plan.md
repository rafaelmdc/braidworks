# Wikidata proposed implementation plan

Status proposed. [Spec](wikidata.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-WIKIDATA-01 | 001,002,003,006 | Source-local validated SPARQL adapter/projection and retry policy; shape/control400/order/conflict/budget fixtures, keep chunk recovery. |
| WP-WIKIDATA-02 | 004,007 | Explicit config/owned-client identity, accurate UA/docs/examples/current source sample. |
| WP-WIKIDATA-03 | 005 conditional | Review stable-ID map/describe and language scope; keys/params/group compatibility, source samples/goldens. |

Accepted issues before coding; package tests/strict/lint/live E2E after API edits.
Retain conformance, review candidates and pacing; patch versions and catalogs as needed.
No generic query engine or class hierarchy per property.
