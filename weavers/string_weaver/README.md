# string_weaver

STRING protein–protein interactions — a molecular weaver off the protein hub, over the
free, keyless STRING REST API. Lists a protein's interaction partners with confidence
scores and per-evidence-channel subscores.

- **Source:** https://string-db.org · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkac1000 — STRING (Szklarczyk et al.)
- **Backend:** `api` (keyless) · **Discoverable as** `string`

## Capabilities

| Capability | Consumes | Produces |
|---|---|---|
| `list_interactions` | `protein.uniprot.accession` | **`protein.query`** (⤜ fan: each partner name), `protein.interaction.partners`, `protein.interaction.count`, `protein.interaction.records` (full edges: partner, combined score, per-channel subscores) |

STRING maps the accession to its protein + species itself, so this is single-input and
reachable directly off the hub. It emits each partner name as **`protein.query`** (a set
output) — the same key `uniprot_weaver` consumes — so fanning out re-resolves each partner
back through UniProt: `protein → partners → fan → each partner's UniProt entry`.

## Deterministic ordering

STRING returns partners ranked by confidence, but ties are not ordered stably. The backend
imposes a fixed total order — **combined score descending, then partner name ascending** —
and caps the display at `limit` (default 25). So the same accession always yields the same
partner list. An identifier STRING can't map (HTTP 400/404) is a clean `NO_MATCH`.

## Use it

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run string list_interactions --have protein.uniprot.accession=P04637
braidworks weave --have protein.query=P04637 --want protein.interaction.partners   # routed via uniprot
```

From Python:

```python
from string_weaver import build_string_weaver

weaver = build_string_weaver()        # zero-config
# In an app that wires a WeaverFactory, `string_weaver.register(factory)` adds it as a provider.
```

## Develop

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live STRING API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](../../AGENTS.md).
