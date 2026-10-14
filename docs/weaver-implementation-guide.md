# Implement a weaver

A weaver connects one biological source to Braidworks through shared identifiers.
Start with the source's real data and a spec, generate the package, then implement
its backends. The scaffold supplies the manifest, dispatch and mapping structure;
your work is to retrieve observations and normalize them into the declared outputs.

This guide is for contributors adding a source. Follow [repository rules](../AGENTS.md)
and use the generated `IMPLEMENTATION.md` as the package's worklist. For the design
behind the shared runtime, read [architecture](architecture.md) and
[toolkit decisions](../weaverkit/docs/decisions.md).

## Define the source contract

Before scaffolding, answer these questions in `weaver.spec.toml`:

| Decision | What to establish |
|---|---|
| Source and provenance | Name, title, source URL, data license, citation and attribution. Include an observed `source_sample`, not an invented schema. |
| Inputs | Registered keys that identify or resolve source records. Check the [key index](keys-index.md) for producers and consumers. |
| Outputs | Useful fields and identifier bridges. Group outputs computed by the same source operation. |
| Lookup shape | `lookup` for clean identifier lookup; `resolver` for fuzzy or ambiguous matching with candidates and review. |
| Backends | Local data, API, or both; declare capability-specific availability when they differ. |
| Parameters | Filters, thresholds and other per-query controls with deterministic defaults. |
| Source identity | Release, dump date, content checksum or effective API contract/scope used for cache invalidation. |
| Verification | Known input/output examples, an offline fixture and, for an API, a live known-truth test. |

Choose inputs from the [shared-key registry](../weaverkit/src/weaverkit/keys.py).
Entry keys such as `organism.name` are valid. Prefer connections to existing
producers; an unmet input remains usable when callers supply it directly. Add a
new bridge key deliberately in the same change if the registry lacks a suitable key.

Name capabilities by their lookup shape: `resolve_*` for ambiguous matching,
`list_*` for related sets, `describe_*` for one entity, and `map_to_*`/`map_from_*`
for identifier cross-references. A list's expandable identifier should be consumed
by its describe capability or another source.

Multiple `consumes` keys normally mean all are required; the planner does not route
such conjunctions as ordinary graph edges. Set `consumes_any = true` for alternative
inputs and dispatch on the supplied key. Declare fan dimensions in `set_outputs`;
these must be produced shared keys. Use parameters for how a lookup operates, output
groups for which fields it computes, and separate capabilities for distinct lookups.
See the [spec field reference](../weaverkit/README.md#weaverspectoml-field-reference).

## Validate and scaffold

Run from the repository root after [contributor setup](../CONTRIBUTING.md).
Replace `your_source` and the spec path with your chosen names:

```bash
make verify-weaver SPEC=path/to/weaver.spec.toml
make new-weaver SPEC=path/to/weaver.spec.toml DEST=weavers/your_source_weaver
make sync
```

Keep the draft spec outside `weavers/` until scaffolding. The workspace treats each
child there as a package, so a spec-only directory breaks workspace resolution.
Scaffolding copies the spec into the destination. Workspace membership and root lint
paths already include weaver packages; no manual root additions are needed.

The package starts with this division of responsibilities:

| Location | Your work |
|---|---|
| `weaver.spec.toml` | Maintain capabilities, provenance, parameters and golden expectations. |
| `src/<package>/vocab.py` | Generated manifest. Change the spec and use [safe regeneration](../weaverkit/docs/safe-regeneration.md), rather than editing it by hand. |
| `src/<package>/weaver.py` | Thin assembly over core's dispatch and mapper. Keep shared behavior in core. |
| `src/<package>/backends/` | Implement configuration checks, source identity and batch fetches. |
| `src/<package>/factory.py` | Keep discovery construction cheap; add configured construction and fixture wiring as needed. |
| `src/<package>/setup.py` | Generated for a bulk source: implement building and artifact validation. |
| `src/<package>/fixture.py` | Present for applicable scaffolds, or add it for deterministic golden execution. |
| `tests/` | Complete backend behavior, conformance, contract and opt-in live checks. |
| `IMPLEMENTATION.md`, `CONTRIBUTING.md` | Track initial completion; document source-specific extension rules and limitations. |

The scaffold also supplies package metadata, a Makefile and the discovery entry point.
Preserve `[project.entry-points."braidworks.weavers"]`. Do not regenerate over an
implemented package with `--force`: it replaces files, including backends and tests.

## Implement the backend

Implement `BackendBase` through the generated backend stub. Core's
[backend contract](../braidworks-core/src/braidworks/core/backend.py) defines `fetch`:
it receives a batch of input dictionaries, requested outputs, resolved groups to
compute, and effective parameters when declared. Return exactly one record per query
in input order, including misses and errors. Internal deduplication must restore the
original positions, including duplicate inputs.

Use core `LookupRecord` or `ResolverRecord` values keyed by produced type IDs.
The shared mapper converts them into strands and filters output coverage; shared
dispatch selects the backend and computes groups. Gate expensive work on
`groups_to_compute`, and read validated/defaulted query controls from `params`.
Keep source-specific types and normalization in the weaver; core stays domain-neutral.

The [backend implementation reference](../weaverkit/docs/implementing-backends.md)
contains the field contracts and fetch patterns. Start with the
[example backend](../weavers/example_weaver/src/example_weaver/backends/local.py)
for a small offline implementation. Preserve these behaviors:

- Construct backends cheaply. Missing local data means `is_configured()` is false;
  an explicit configured builder can report an actionable configuration error.
- Return a stable source identity from `fingerprint()`, never an empty string or
  `unknown`. Local identities must change with the served artifact. Live API identity
  describes its contract and effective scope; it does not freeze provider contents.
- Represent per-input misses and failures as records. HTTP 400/404 are no-match under
  the project's fetch convention; 5xx/network failures are errors. Use
  `is_not_found_status` and preserve source-specific interpretation where needed.
  Structural faults use the documented configuration/capability/backend exceptions.
- Order candidates deterministically with an identifier tiebreak. Deduplicate, sort
  and cap display lists while reporting true totals. Expandable set keys retain the
  full distinct ordered set, not the display cap. Preserve review requirements for
  ambiguous or low-confidence resolution.
- Use upstream bulk endpoints in chunks rather than one request per input. For
  single-ID APIs, use bounded concurrent work. Map responses back by stable identity
  or echoed query and test request counts/order. Honor pacing through the scaffold's
  shared HTTP seam; see [request pacing](request-pacing.md).

## Configure data and resource ownership

Keep a zero-argument `build_<package>()` that exposes the complete manifest without
network acquisition, even when local data are unconfigured. Add a configured builder
for database paths, endpoint/client settings or credentials. A fixture builder provides
small deterministic data for strict goldens; fixtures are not research reference data.

Entry-point discovery and registering a built instance in `BraidRegistry` support
execution. `register(factory)` registers a provider with the optional `WeaverFactory`;
it is not required to make an installed package discoverable. Validate builder options
and document where configured helpers are imported. See
[configuration and client ownership](weaver-configuration.md) for borrowed clients,
closing owned resources and effective endpoint identity.

For bulk data, implement the generated build/validation hooks over
[core local acquisition](../braidworks-core/src/braidworks/core/localdb.py). Preserve
consent, path selection, locking, validation and atomic publication. Store source and
build identity in the artifact. Keep databases/dumps/archives out of git. Document
required space, refresh behavior and the need to reopen a backend after replacing its
pinned data generation. A tiny bundled teaching fixture is a separate case.

[NCBI setup](database.md) shows an implemented acquisition workflow. Reuse a compatible
parser only after checking the actual source format; a source's name alone does not
establish compatibility with NCBI taxdump.

## Verify the complete source path

Add real `[[golden]]` examples whose inputs and expectations are supported by your
fixture. Populate mock API responses with observed schemas. Keep ordinary tests
independent of network/data acquisition; supply a fixture builder to conformance and
contract tests. Replace `TODO-real-input` in the opt-in live test.

Run these from the repository root, substituting the actual package name:

```bash
make verify-weaver SPEC=weavers/your_source_weaver/weaver.spec.toml PACKAGE=your_source_weaver
make -C weavers/your_source_weaver test
uv run weaverkit verify --spec weavers/your_source_weaver/weaver.spec.toml \
    --package your_source_weaver --strict
make lint
make test
```

Plain verification checks structure; it can skip goldens. Strict verification requires
completed implementation and executable goldens. Include tests for exact/missing/error
results, ambiguity when supported, output groups/parameters, batch length/order and
fingerprint identity. Preserve conformance/contract checks; fix implementation failures
rather than weakening the tests. Public boundary dataclasses must round-trip through
`to_json()`/`from_json()`. Package suites depend on their working directory, so use
Makefile targets.

After touching an API backend, also run its known-truth live check:

```bash
BRAIDWORKS_RUN_LIVE=1 make -C weavers/your_source_weaver test-live
```

Mocked checks cannot establish that today's upstream schema still matches. Diagnose
live failures by comparing an observed response to the mock. Document validation limits
if the live source cannot be reached.

Finally, rebuild the catalogue with `make index`, inspect producers/consumers and test
a route from supplied input to a useful output. Keep the three weaver version sites
(spec, package metadata and generated `WEAVER_VERSION`) consistent. Behavior/manifest
changes need the appropriate bump and minimum core version; depend on a floor without
a ceiling. Tags follow the automated release workflow.

## Extend handwritten machinery only when needed

NCBI retains domain-specific intermediate records, mapping and dispatch. Those files
are a reference for extending an existing handwritten implementation, not a template
for duplicating core in a new package. Its custom `vocab.py` is the documented exception
to generation; replacing it with scaffold output loses constants.

If a source needs richer internal records, keep one backend-neutral mapping boundary,
maintain the same batch/status/group/review guarantees, and justify the extra machinery
with a source requirement. Consult [core contracts](core-contracts.md) and the
[NCBI source](../weavers/ncbi_weaver/src/ncbi_weaver/) before changing that boundary.
