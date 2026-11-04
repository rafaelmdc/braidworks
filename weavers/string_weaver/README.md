# string_weaver

Retrieve bounded protein functional-association networks from STRING with combined scores and
evidence channels. Associations can include indirect functional relationships and need not
represent physical binding. The keyless API supports species, score and retrieval controls; its
observed count is not an exhaustive interaction network.

- **Source:** https://string-db.org · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkac1000 — STRING (Szklarczyk et al.)
- **Backend:** `api` (keyless) · **Discoverable as** `string`

## Capabilities

| Capability | Use it to |
|---|---|
| `list_interactions` | Retrieve a bounded functional-association network |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

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
