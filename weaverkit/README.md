# weaverkit

Use weaverkit to create and verify a source adapter, inspect the installed source
network, or run queries in a local browser. Query planning, execution and shared
backend machinery live in `braidworks-core`; this package supplies authoring and
visual tools.

## Run queries in the browser

Install the `serve` extra with your selected sources, then run `weaverkit serve`.
Follow [the browser guide](../docs/browser.md) to build a route, process a batch,
export results or continue saved work. The optional server uses FastAPI and uvicorn;
the base toolkit depends on core and its networkx/platformdirs dependencies.

For an offline network view, use `weaverkit view --out network.html`. It writes a
self-contained HTML file without CDN dependencies. Add `--from`/`--to` for a planned
route, or `--run result.json` for the lineage of a serialized `ExecutionResult`.
Set-valued keys are marked as fan dimensions. See `weaverkit view --help`.

## Build or extend an adapter

Follow [the implementation guide](../docs/weaver-implementation-guide.md):
write a spec, scaffold the package, implement source backends, then verify it.
The scaffold imports records, mapping and dispatch from core. Conformance checks
compare the implementation to the spec; strict verification adds completed goldens.

| Task | Guide or command |
|---|---|
| Define inputs, outputs, parameters and provenance | [Spec reference](docs/spec-reference.md) |
| Generate a new package | `weaverkit new --spec PATH --dest PATH` |
| Verify the source contract | `weaverkit verify --spec PATH --package PACKAGE --strict` |
| Implement backend behavior | [Backend reference](docs/implementing-backends.md) |
| Extend an implemented package safely | [Safe regeneration](docs/safe-regeneration.md) |
| Inspect/write scaffold artifacts from Python | [Scaffold interfaces](docs/scaffold-reference.md) |
| Find source connections | `weaverkit index`; [key index](../docs/keys-index.md) |
| Inspect source attribution | `weaverkit references` |

The index scans workspace specs and writes capability/input/output/backend metadata;
`unmet_inputs` is a connectivity hint, not a verification failure. The view and references
commands report broken plugins while retaining valid ones. Queries use strict discovery;
see [discovery reference](../docs/reference/discovery.md).

## `weaver.spec.toml` field reference

Exact fields now live in [the spec reference](docs/spec-reference.md). This heading
retains the route from existing contributor links.

## Why specs use TOML

TOML supplies explicit string/number types and a standard-library parser (`tomllib`),
matching the workspace's `pyproject.toml`. Nested array-of-table syntax costs verbosity;
semantic validation reports contract errors after parsing. The format is a maintained
contract, so edit and validate it as capabilities change. See [design decisions](docs/decisions.md)
for the shared runtime, builder and verification rationale.

## Installation and interfaces

Use [checkout or wheel installation](../docs/installation.md); publication to a package
index is not assumed. The [browser interface reference](../docs/reference/browser.md)
records HTTP endpoints and generated artifacts. [Current work](docs/backlog.md) tracks
pending toolkit changes; it is separate from current usage instructions.

## Software license

The software uses [MIT](LICENSE). Provider data and source samples retain their own
licenses and attribution requirements as declared by each weaver.

Refresh spec-owned capability tables with `weaverkit capability-docs --root .`; add
`--check` to detect drift without writing. See [inventory generation](docs/scaffold-reference.md#generated-capability-inventories)
for marker ownership and workspace commands.
