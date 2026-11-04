# Error boundary review — #133

The issue has no body or acceptance criteria. Current code already separates structural
exceptions, unavailable-backend fallback, branch-local failure values and review policy.
The executor, runner and ARQ transport tests cover those boundaries. A replacement error
hierarchy or mandatory new error envelope has no established requirement.

## Verified gap and plan

`classify_error` searches HTTP status digits as arbitrary substrings. Identifiers such
as `1500123`, `AF-P40300` and filenames can therefore classify an unrelated failure as
an upstream outage, authentication problem or rate limit. Classification must recognize
standalone HTTP-status tokens, preserve the existing text fallback and prefer an actual
HTTP status over ambiguous message wording. Explicit missing-configuration phrases should
classify as configuration when no HTTP status is present. Typed exception classification
continues to use the observed response status or exception type.

Implement that small pure-function refactor, regression-test identifiers/statuses/config
and transport behavior, and publish a single reference for exception/result boundaries.
Preserve public classes, persisted error shapes, fallback policy and unknown-error behavior.
No new exception family, mandatory adapter migration or speculative retry framework.
Close #133 as reconciled with this concrete scope after core/ARQ/toolkit checks.

## Acceptance

Implemented 2026-10-15. Identifier/version fragments no longer become HTTP statuses;
standalone status tokens and transport classification remain supported. Explicit missing
configuration is distinguished from authentication rejection. The new failure reference
records existing exception/value/fallback behavior and the limits of string inference.
Lint, core (581), ARQ (118, two skips) and toolkit (295) passed. Documentation validation
checked 1,287 links/anchors in 242 documents; whitespace passed. Public exception classes
and error serialization shapes are unchanged. No broad hierarchy rewrite was justified.
