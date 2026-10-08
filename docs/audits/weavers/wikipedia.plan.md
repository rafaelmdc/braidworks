# Wikipedia proposed implementation plan

Status proposed. [Spec](wikipedia.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-WIKIPEDIA-01 | 001,002,003 | Review metric compatibility/default migration; pure effective measurement scope shared by identity/window/query/build, month mismatch and API/local parity fixtures. |
| WP-WIKIPEDIA-02 | 004,005 | Validated per-title adapter/reducer, bounded distinct calls, explicit config/lifecycle; malformed/sibling/pacing/cancellation cases. |
| WP-WIKIPEDIA-03 | 006,007 | Validated streaming source/checksum/coverage and honest title/docs/examples; tiny dump/source fixture, no forced GB download. |
| WP-WIKIPEDIA-04 | 007 conditional | Review monthly series/project/agent/access/window params with coherent title provenance; source samples/manifest/goldens. |

Accepted issues before coding; tests/strict/lint and bounded live known article after API
edits. Keep conformance/source-binding and streamed build; versions/floor/catalogs updated
as needed. Cache/resume and large historical aggregation remain separately reviewed.
