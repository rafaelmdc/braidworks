# Core contracts for contributors

Use this reference when implementing a weaver or changing framework behavior. The
[architecture](architecture.md) explains why these boundaries exist;
[AGENTS.md](../AGENTS.md) specifies the repository's mandatory contribution rules.
Exact signatures and serializers live beside their implementations, linked below.

## Data and declarations

| Contract | Implementation |
|---|---|
| `Strand` carries a JSON value, confidence, provenance, and metadata; treat it as immutable after construction. | [strand.py](../braidworks-core/src/braidworks/core/strand.py) |
| Construct a `StrandSet` with `from_strands`; read with `get`, `has`, and `available_types`. The executor owns mutation while running. | [strand.py](../braidworks-core/src/braidworks/core/strand.py) |
| Capabilities declare inputs, outputs, groups, backends, batch limit, cost, parameters, alternative inputs, and expandable set keys. | [capability.py](../braidworks-core/src/braidworks/core/capability.py) |
| Each produced type belongs to exactly one output group. Invalid manifests fail registration. | [registry.py](../braidworks-core/src/braidworks/core/registry.py) |
| Shared input keys must be registered. Cardinality is declared with `set_outputs`; suffix spelling alone does not determine expansion. | [Shared keys](../braidworks-core/src/braidworks/core/keytypes.py) and [repository rules](../AGENTS.md) |

An output group describes fields computed together. Requesting any field in a group
triggers that group. Backends may compute prerequisite groups internally, reporting
all computed groups so cache coverage remains honest. A missing optional provider
field must preserve its documented missing-value semantics rather than invent data.

## Batch execution and failures

`execute_batch` returns exactly one `WeaveResult` per input, in input order. Missing
and failed inputs retain their positions. Shared dispatch and execution validate the
count; mismatches raise `BatchContractError` before mapping/caching/merging. Equal-length
reordering still requires source-side correlation tests.

Backends bulk upstream requests when the source supports it; truly single-ID APIs
use bounded concurrency. The executor's `max_batch_size` and a provider's bulk/chunk
limit are separate. See [BaseWeaver](../braidworks-core/src/braidworks/core/weaver.py),
[shared dispatch](../braidworks-core/src/braidworks/core/dispatch.py), and
[backend implementation patterns](../weaverkit/docs/implementing-backends.md).

| Condition | Representation |
|---|---|
| Successful observation | `WeaveStatus.OK` with strands and computed groups |
| No source match | `WeaveStatus.NO_MATCH`; a lookup outcome, not proof of biological absence |
| Ambiguous result | `WeaveStatus.AMBIGUOUS` with candidates and review context |
| Expected per-input source failure | `WeaveStatus.ERROR` with diagnostics |
| Invalid/broken backend configuration | `BackendConfigurationError`, a run-level exception |
| Implemented backend unavailable in this instance | `BackendUnavailable`, eligible for configured fallback |
| Broken batch count | `BatchContractError`, a run-level exception without fallback |

Programming errors and cancellation must not be broadly caught and disguised as
biological misses. Confidence and `requires_review` remain independent; automatic
selection retains review flags. See [result.py](../braidworks-core/src/braidworks/core/result.py)
and [execution outcomes](results.md).

## Routing and fallback

The registry uses a multigraph so competing routes survive. It projects single-input
capabilities and each `consumes_any` alternative; conjunctions needing several inputs
are not projected. The planner consumes sets of available and target types and
returns a serializable `Braid` with explicit backend assignments. `from_types` holds
the minimal required external inputs, not every supplied field.

| Policy | Preference | Default fallback conditions |
|---|---|---|
| `LOCAL_ONLY` | local | None |
| `API_ONLY` | api | None |
| `LOCAL_FIRST` | local, api | No match; backend unavailable |
| `API_FIRST` | api, local | No match; backend unavailable |

A configured `ERROR` fallback is distinct from default fallback behavior.
`BackendConfigurationError` never becomes an ordinary fallback condition. No type
route raises `NoPathError`; routes excluded by policy raise `NoPlanError`. Runtime
source availability is separate from declared routability.

See [planner.py](../braidworks-core/src/braidworks/core/planner.py),
[braid.py](../braidworks-core/src/braidworks/core/braid.py), and
[executor.py](../braidworks-core/src/braidworks/core/executor.py).

## Cache identity and coverage

`StrandCacheKey` includes weaver ID/version, capability, backend, backend fingerprint,
and a hash of consumed values plus effective parameters. Unrelated input strands and
provenance do not affect that hash. Results are stored under the backend that actually
produced them. Never return an empty or `unknown` fingerprint.

Requested groups are separate from the base key. A cached result satisfies a request
when its `computed_groups` cover the requested groups. Successful and no-match
observations may be cached; errors are not. Cached ambiguity retains review context.
The memory cache and optional SQLite cache implement the same `get`/`put` protocol;
SQLite adds policy-driven expiry and storage limits.

See [cache.py](../braidworks-core/src/braidworks/core/cache.py) and
[persistence reference](persistence.md#storage-and-api-reference). A source/interface
fingerprint and TTL cannot establish that a mutable provider dataset is frozen.

## Expansion, continuation, and serialization

Expansion reserves the shared leaf budget before allocating children. Every input
root remains represented. Exported row identity and result-scoped entity references
handle duplicate human labels; those labels are not globally unique database keys.
Partial success can carry branch errors, so summing result-bucket lengths is not a
valid input count. Use `total()` and `fatal_errors()`; see [results](results.md).

Managed runs save complete query-state snapshots between applied waves. The run store
uses revisions and bounded ownership leases; storage transactions exclude source
calls and human waits. Saved identities/settings are validated before continuation.
Completed state returns saved results; an interrupted unsaved read may repeat.

Public boundary dataclasses round-trip through `to_json()` / `from_json()`. Keep
[contract tests](../braidworks-core/src/braidworks/testing/contract.py) and
[weaver conformance tests](../weaverkit/src/weaverkit/conformance.py) intact when
changing these boundaries. Configuration/lifecycle rules are in
[weaver configuration](weaver-configuration.md).
