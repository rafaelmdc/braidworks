# Failure contract

Use this page to distinguish exceptions that stop a run from result values that
retain an entity's partial data. See [result inspection](../results.md) for commands
and [result meaning](../explanation/result-meaning.md) for biological interpretation.

## Exceptions

All classes below inherit `BraidworksError`, exported by `braidworks.core`.

| Exception | Meaning | Handling |
|---|---|---|
| `InvalidManifestError` | Invalid or inconsistent adapter metadata | Registration fails before routing. Fix the declaration. |
| `NoPathError` | No connecting route exists for the requested types | Choose reachable outputs or register an appropriate weaver. |
| `NoPlanError` | A declared route is blocked by enabled backends/policy, or explicit traversal is invalid | Inspect its source/capability/backend context and query selection. |
| `UnsupportedCapability` | A direct caller named an unimplemented operation | Correct the capability ID. |
| `BackendUnavailable` | A known operation/backend cannot run in this instance | Executor may try the next backend under `BACKEND_UNAVAILABLE`; exhaustion becomes a recorded error. |
| `BackendConfigurationError` | A structural/configuration problem prevents a valid run | Propagates immediately; never converted into an ordinary miss or fallback. |
| `BatchContractError` | Runner/backend returned an invalid batch | Propagates; results cannot safely be aligned to entities. |
| `ReviewRequired` | Review policy explicitly requires an exception | Choose a review policy or supply a reviewed continuation. |
| `MissingInputError` | Required starting strands are absent | Normally recorded by executor preflight as an input error. |

Argument/schema validation may raise `ValueError` or `TypeError`. File and storage
operations can also raise their native exceptions. Unexpected programming exceptions
and cancellation propagate; adapters must not catch everything and report `NO_MATCH`.

## Result failures

A backend returns `NO_MATCH` for a valid identifier with no matching source data and
`ERROR` for an entity-level technical failure. These are values, not structural
exceptions. Ordinary `NO_MATCH` is not an error and does not prove biological absence.
Fallback for `NO_MATCH` or `ERROR` follows the invocation's configured conditions.

Under the default collect policy, failed branches retain their diagnostics and do not
discard successful sibling outputs. `ErrorPolicy.RAISE` raises `BraidworksError` for
an entity-level `ERROR`. Review-required outcomes follow the separate review policy.
Persisted `ExecutionError` records retain category, message and step/capability context.

## Diagnostic categories

`ErrorCategory` describes why a failure occurred; it is independent of exception type
and does not decide fallback. Values include `upstream_unavailable`, `rate_limited`,
`timeout`, `network`, `auth`, `not_found`, `bad_response`, `config`, `input` and `unknown`.

`classify_exception` uses an observed HTTP response status or transport exception type
when available. `classify_error` is a best-effort fallback for existing string errors:
standalone HTTP-status tokens take precedence over wording, followed by known message
phrases. Status digits embedded in accessions, larger identifiers or version fragments
are ignored. A standalone number in arbitrary prose can still be ambiguous; this
helper cannot reconstruct source evidence from text. Preserve the original message and
inspect it when a classification appears wrong. Unknown failures remain `unknown`.
