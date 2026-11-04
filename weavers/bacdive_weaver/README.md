# bacdive_weaver

Retrieve strain phenotypes and source evidence from BacDive. A scientific-name trait lookup
selects a type-strain representative; exact strain IDs and collection/genome mappings support
strain-specific work. A representative does not describe every isolate of a species. The API is
keyless.

- **Source:** https://bacdive.dsmz.de · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkab961 — BacDive (DSMZ)
- **Backend:** `api` (keyless) · **Discoverable as** `bacdive`

## Capabilities

| Capability | Use it to |
|---|---|
| `describe_traits` | Retrieve representative type-strain traits |
| `list_strains` | List observed type and non-type strains |
| `describe_strain` | Inspect an exact strain |
| `map_to_strain` | Map collection/genome identifiers to strain IDs |
| `map_from_strain` | Map strain IDs to observed collection/genome references |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run bacdive describe_traits --have organism.scientific_name="Escherichia coli"
braidworks weave --have organism.name="Escherichia coli" --want microbe.trait.gram_stain   # routed via taxon
```

From Python:

```python
from bacdive_weaver import build_bacdive_weaver

weaver = build_bacdive_weaver()        # zero-config
# In an app that wires a WeaverFactory, `bacdive_weaver.register(factory)` adds it as a provider.
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
