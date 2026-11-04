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

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.


### SH-03 implementation (2026-10-09)

Completed the #150 response-validation/failure-isolation scope for #282, #283, #287. SPARQL envelopes and bindings are validated before accumulation. Query/service HTTP 400/404 is an error, never evidence of taxon absence; it is not retried. Taxon absence is a valid empty bindings list. Query literals escape quotes, backslashes and control characters. Each chunk has at most four attempts within a 90-second elapsed budget (including request time and waits); Retry-After seconds/HTTP dates are honored when they fit, otherwise the chunk fails without retrying early. Errors retain the final reason. expected_rank remains a homonym disambiguator: it chooses a uniquely matching rank only among multiple items and does not reject a single item with another rank.

See [SH-03 implementation evidence](SH-03.implementation.md) for changes, migrations, exact verification and remaining scope. Other work packages/findings in this source plan remain separately tracked.

## SH-08 identity implementation

Primary shared identity findings are implemented under #155; see
[SH-08 implementation and validation](SH-08.implementation.md). Source-specific
work packages with additional feature proposals remain tracked by their own groups.

Shared documentation findings in #148 are implemented; see
[SH-01 evidence and scope](SH-01.implementation.md). Other source capability and
configuration work remains owned by its existing issues.

Shared configuration/lifecycle findings in #149 are implemented; see
[SH-02 acceptance, verification and migrations](SH-02.implementation.md).
Source-specific remaining proposals and capabilities stay separately tracked.
