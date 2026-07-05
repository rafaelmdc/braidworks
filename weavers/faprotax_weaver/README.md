# faprotax_weaver

FAPROTAX ecological function (organism lineage -> functional groups) weaver for Braidworks.

- **Source:** https://pages.uoregon.edu/slouca/LoucaLab/archive/FAPROTAX/
- **License:** Open
- **Cite:** https://doi.org/10.1126/science.aaf4507

The contract lives in [`weaver.spec.toml`](weaver.spec.toml).

## What it does

Consumes an organism's `ncbi.taxon.lineage` (as produced by `ncbi_weaver`) and
produces `microbe.ecology.functional_groups` — the FAPROTAX ecological/metabolic
functional groups the organism's clade is affiliated with (e.g. `methanotrophy`,
`nitrification`, `sulfate_respiration`, `fermentation`). FAPROTAX defines ~90
groups, each as member taxon patterns (`*Level*Level*` — an ordered,
case-insensitive subsequence over the lineage names); a taxon inherits a group if
any ancestor in its lineage matches. A taxon matching zero groups is a miss
(FAPROTAX only annotates clades of established function).

The `local` backend serves a bundled copy of `FAPROTAX.txt` (~950 KB, v1.2.12) —
no network or download. Parsing (incl. recursive `add_group:` resolution) and
matching live in `src/faprotax_weaver/backends/local.py`.

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
