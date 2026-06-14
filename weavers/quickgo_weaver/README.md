# quickgo_weaver

Gene Ontology annotations via EBI QuickGO — a molecular weaver off the protein hub, over
the free, keyless QuickGO REST API. Lists the GO terms annotated to a protein (grouped by
the three GO aspects), and drills any single term into its definition.

- **Source:** https://www.ebi.ac.uk/QuickGO · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/bioinformatics/btp536 — Gene Ontology / EMBL-EBI QuickGO
- **Backend:** `api` (keyless) · **Discoverable as** `quickgo`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `list_go_terms` | `protein.uniprot.accession` | **`go.term`** (⤜ fan: every distinct GO id), `go.molecular_function`, `go.biological_process`, `go.cellular_component` (term-name lists), `go.count`, `go.records` |
| `describe_go_term` | `go.term` | `go.term.name`, `go.term.aspect`, `go.term.definition`, `go.term.detail` |

`list_go_terms` emits `go.term` as a **set output** (the fan dimension), and
`describe_go_term` consumes it — so a fanned term is drillable end-to-end.

## Dedup + deterministic ordering

QuickGO returns **one row per annotation evidence**, so a single protein yields hundreds
of rows across many pages. The backend paginates (up to a page cap, default 10 × 200 =
2000 annotations — truncation is logged, not silent), **dedups to distinct GO terms**, and
sorts them by GO id. So the same accession always yields the same lists. An accession with
no annotations is a clean `NO_MATCH`.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run quickgo describe_go_term --have go.term=GO:0006915
braidworks weave --have protein.query=P04637 --want go.biological_process   # routed via uniprot
# fan one protein out into each GO term's definition:
braidworks weave --have protein.query=P04637 --want go.term.name --expand all
```

From Python:

```python
from quickgo_weaver import build_quickgo_weaver

weaver = build_quickgo_weaver()        # zero-config
# In an app that wires a WeaverFactory, `quickgo_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live QuickGO API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](../../AGENTS.md).
