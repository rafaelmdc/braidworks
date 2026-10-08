# FAPROTAX proposed implementation plan

Status proposed. [Spec](faprotax.spec.md).

| Work package | Findings | Work |
|---|---|---|
| WP-FAPROTAX-01 | 001,002,003,004 | Acquire/read bounded official matcher reference, define NCBI-name translation; pure ordered rule parser/evaluator; real binomial/exclusion/operator differential fixtures. |
| WP-FAPROTAX-02 | 004,005 | Accurate putative inference/docs/examples, safe regeneration and explicit builder; source grammar update guide. |
| WP-FAPROTAX-03 | 003 conditional | Review evidence/group attribute outputs; observed reference samples, manifest/goldens. |
| WP-FAPROTAX-04 | 006 conditional | Profile batch matcher, optimize immutable rules/memoization only if warranted. |

Open accepted work issues before coding. Package tests/strict/lint; no live backend/build
required. Preserve bundled source and contracts, patch version sites, regenerate catalogs
only for accepted manifest changes. No unnecessary inheritance/repository framework.

Tracking update: [individual finding issues and shared/source groups](issue-hierarchy.md)
are open under #147. Use those issues for work-package acceptance and evidence. Necessary
breaking changes are permitted; document affected interfaces, migrations and version updates.
