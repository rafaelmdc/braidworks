# faprotax_weaver

FAPROTAX ecological function (organism lineage -> functional groups) weaver for Braidworks.

- **Source:** https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/
- **License:** Open
- **Cite:** https://doi.org/10.1126/science.aaf4507

The contract lives in [`weaver.spec.toml`](https://github.com/rafaelmdc/braidworks/blob/main/weavers/faprotax_weaver/weaver.spec.toml).

## What it does

Consumes an organism's `ncbi.taxon.lineage` (as produced by `ncbi_weaver`) and
produces `microbe.ecology.functional_groups` — the FAPROTAX ecological/metabolic
functional groups the organism's clade is affiliated with (e.g. `methanotrophy`,
`nitrification`, `sulfate_respiration`, `fermentation`). FAPROTAX defines ~90
groups, each as ordered, case-insensitive complete-word patterns (`*Level*Level*`).
The words are matched over the full lineage text, so `*Methanosarcina*barkeri*`
matches the NCBI binomial `Methanosarcina barkeri`. Word boundaries prevent suffix
and hyphenated-word false positives. A taxon matching zero groups is a miss
(FAPROTAX only annotates clades of established function).

The `local` backend serves a bundled copy of `FAPROTAX.txt` (~950 KB, v1.2.12) —
no network or download. The private pure parser/interpreter in `rules.py` honors ordered `add_group:`,
`subtract_group:` and `intersect_group:` operations. References must target earlier
groups; missing references, cycles and malformed definitions are explicit source errors.
Group attributes and rule literature comments are retained in immutable parsed rules.
A public evidence-output group remains a separate scope proposal.

## Licensing & attribution

FAPROTAX is distributed under a **custom BSD-3-Clause-style license** (© Stilianos
Louca); redistributions must retain its copyright notice and disclaimer, and any
modification must be clearly indicated. The bundled `FAPROTAX.txt` is included
**verbatim and unmodified**, so its embedded license header satisfies the notice
requirement. It is recorded in the spec as `license = "Open"` (nearest known
identifier) with citation and attribution.

- **Cite:** Louca, Parfrey & Doebeli (2016), *Science* — https://doi.org/10.1126/science.aaf4507
- **Database:** © Stilianos Louca — https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/

```bash
make verify   # check the weaver still matches its spec
make test     # run conformance + contract + golden tests
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import faprotax_weaver

factory = WeaverFactory()
faprotax_weaver.register(factory)        # makes "faprotax" buildable
```

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/faprotax_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.

## Batch-local matching (0.1.2)

Parsed bundled rules are immutable. Matching runs in a worker thread and scans
once per distinct case-insensitive lineage within a batch. Each result receives
a separate list; query results are not cached across batches. This preserves sorted outputs and miss semantics while applying the source-compatible
word and set-operation rules described above.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.

## CLI example through NCBI lineage

```bash
braidworks weave --have organism.name=Methylococcus --want microbe.ecology.functional_groups --policy api_first
```

This routes through NCBI to obtain the structured lineage (network access
required), then matches bundled FAPROTAX rules locally. The CLI’s table/scalar
input format does not directly represent a lineage list; use Python for direct
structured lineage calls. Affiliation is a putative taxonomy-based inference,
not proof of function in each strain.

## Explain an affiliation

Request `microbe.ecology.evidence` from `describe_ecology` for source identity,
input lineage, group attributes, retained literature and membership traces. The
same evaluator computes names and traces: matched member patterns and all ordered
add/subtract/intersect operations show before/after states and source lines.
Unmatched member patterns are counted rather than copied into the trace.

An explicit evidence request can explain an empty membership result; ordinary
functional-group requests still return `NO_MATCH` when no affiliation is found.
Neither outcome proves functional absence, and literature about a clade is not
an experimental measurement of the queried organism. Default lookups do not
construct traces.
