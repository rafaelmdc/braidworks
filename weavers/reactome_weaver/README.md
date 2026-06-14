# reactome_weaver

Curated biological pathways via Reactome — a molecular weaver off the protein hub, over
the free, keyless Reactome ContentService API. The systems-level "what process is it part
of" panel of the protein dossier. Lists every pathway a protein participates in, and
drills any single pathway into its detail.

- **Source:** https://reactome.org · **License:** CC0-1.0 · **Cite:** https://doi.org/10.1093/nar/gkab1028 — Reactome
- **Backend:** `api` (keyless) · **Discoverable as** `reactome`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `list_pathways` | `protein.uniprot.accession` | **`pathway.reactome.id`** (⤜ fan: every distinct pathway), `pathway.reactome.names` (top N), `pathway.reactome.count` (true total), `pathway.reactome.records` |
| `describe_pathway` | `pathway.reactome.id` | `pathway.reactome.display_name`, `pathway.reactome.species`, `pathway.reactome.in_disease`, `pathway.reactome.detail` |

`list_pathways` emits `pathway.reactome.id` as a **set output** (the fan dimension), and
`describe_pathway` consumes it — so a fanned pathway is drillable end-to-end.

## Dedup + deterministic ordering

Reactome maps the accession to its pathways; the backend dedups to **distinct pathways**
(by Reactome stable id) and orders them by stable id. `count` is the true total;
`names`/`records` are the top `limit` (default 30); `pathway.reactome.id` is the full
distinct set (uncapped — the fan dimension). Same accession → same list. An accession with
no pathways (Reactome 400/404, or an empty list) is a clean `NO_MATCH`.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run reactome describe_pathway --have pathway.reactome.id=R-HSA-69488
braidworks weave --have protein.query=P04637 --want pathway.reactome.names   # routed via uniprot
# fan one protein out into each pathway's detail:
braidworks weave --have protein.query=P04637 --want pathway.reactome.display_name --expand all
```

From Python:

```python
from reactome_weaver import build_reactome_weaver

weaver = build_reactome_weaver()        # zero-config
# In an app that wires a WeaverFactory, `reactome_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live Reactome API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](../../AGENTS.md).
