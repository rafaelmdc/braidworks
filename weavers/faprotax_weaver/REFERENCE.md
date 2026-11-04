# Faprotax source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

<!-- weaverkit:capabilities:start -->
| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `describe_ecology` | `ncbi.taxon.lineage` | `ecology`, `evidence` | `local` | — |
<!-- weaverkit:capabilities:end -->

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

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
Request the implemented `evidence` group to retain membership traces and source literature.

## Registering this weaver

The CLI discovers this installed weaver through its entry point. Python applications
can register a built instance directly in `BraidRegistry`. `WeaverFactory` registration
is optional construction support; it makes the builder available by ID, not a route.
For applications using that factory:

```python
from braidworks.core import WeaverFactory
import faprotax_weaver

factory = WeaverFactory()
faprotax_weaver.register(factory)        # makes "faprotax" buildable
```

## Batch-local matching

Parsed bundled rules are immutable. Matching runs in a worker thread and scans
once per distinct case-insensitive lineage within a batch. Each result receives
a separate list; query results are not cached across batches. This preserves sorted outputs and miss semantics while applying the source-compatible
word and set-operation rules described above.

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


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
