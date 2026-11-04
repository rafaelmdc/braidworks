# reactome_weaver

List the pathways observed for a protein, inspect pathway details and contained reactions, and
retain provider evidence. UniProt can supply the accession. The keyless API returns source
observations, not a synthesized biological confidence assessment; display limits and complete
fan sets serve different purposes.

- **Source:** https://reactome.org · **License:** CC0-1.0 · **Cite:** https://doi.org/10.1093/nar/gkab1028 — Reactome
- **Backend:** `api` (keyless) · **Discoverable as** `reactome`

## Capabilities

| Capability | Use it to |
|---|---|
| `list_pathways` | List observed pathways for a protein |
| `describe_pathway` | Inspect a pathway and its evidence |
| `list_reactions` | List reactions for a reconstruction or pathway |
| `describe_reaction` | Inspect one source reaction |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

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

weaver = build_reactome_weaver()  # zero-config
# In an app that wires a WeaverFactory, `reactome_weaver.register(factory)` adds it as a provider.
```

## Setup, interpretation and contribution

Use [checkout or wheel installation](../../docs/installation.md) with core and the
sources needed for your route. From the checkout, prefix commands above with
`uv run --no-sync`; a bare command assumes the environment is activated.
Source installation does not acquire optional biological databases.

[Source reference](REFERENCE.md) retains coverage, selection, failure and resource
rules. [Builder configuration](../../docs/weaver-configuration.md) documents supported
options and ownership; close configured weavers after work completes. See
[contributing](CONTRIBUTING.md) to extend this source, and run package checks from
this package directory. Current installation does not assume package-index publication.

## Software license

The software uses [MIT](LICENSE). Provider data retain their source licenses and
attribution requirements above; the manifest data license does not license this code.
