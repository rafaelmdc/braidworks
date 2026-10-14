# uniprot_weaver

Resolve protein queries, describe exact accessions, and map identifiers to or from the UniProt
hub. Accessions connect to structure, pathway and annotation sources; taxids connect to organism
sources. Gene-symbol search selects one representative, so constrain the organism or use an
exact accession. The API is keyless.

- **Source:** https://www.uniprot.org · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/nar/gkac1052 — UniProt Consortium
- **Backend:** `api` (keyless) · **Discoverable as** `uniprot`

## Capabilities

| Capability | Use it to |
|---|---|
| `resolve_protein` | Select a representative entry for a protein query |
| `describe_protein` | Inspect an exact accession and annotations |
| `map_to_accession` | Map alternative identifier types into UniProt |
| `map_from_accession` | Map a UniProt accession to requested identifier types |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run uniprot resolve_protein --have protein.query=P04637
braidworks weave --have protein.query=TP53 --param organism=9606 --want protein.uniprot.accession,ncbi.taxon.id
braidworks weave --have protein.query=P04637 --want protein.name,ncbi.taxon.id
```

From Python:

```python
from uniprot_weaver import build_uniprot_weaver

weaver = build_uniprot_weaver()  # zero-config
# In an app that wires a WeaverFactory, `uniprot_weaver.register(factory)` adds it as a provider.
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
