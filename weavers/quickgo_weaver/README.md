# quickgo_weaver

Retrieve GO annotations and their evidence, inspect term definitions and hierarchy, or list gene
products associated with a term. The API is keyless. Pagination budgets and source filters can
limit coverage; retain annotation evidence and completeness warnings with the result.

- **Source:** https://www.ebi.ac.uk/QuickGO · **License:** CC-BY-4.0 · **Cite:** https://doi.org/10.1093/bioinformatics/btp536 — Gene Ontology / EMBL-EBI QuickGO
- **Backend:** `api` (keyless) · **Discoverable as** `quickgo`

## Capabilities

| Capability | Use it to |
|---|---|
| `list_go_terms` | List protein annotations with optional evidence |
| `describe_go_term` | Inspect a GO term and hierarchy |
| `list_gene_products` | List gene products observed for a GO term |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run quickgo describe_go_term --have go.term=GO:0006915
braidworks weave --have protein.uniprot.accession=P04637 --want go.annotation.records,go.annotation.coverage --format json
braidworks weave --have protein.query=P04637 --want go.biological_process   # routed via uniprot
# fan one protein out into each GO term's definition:
braidworks weave --have protein.query=P04637 --want go.term.name --expand all
```

From Python:

```python
from quickgo_weaver import build_quickgo_weaver

weaver = build_quickgo_weaver()  # zero-config
# In an app that wires a WeaverFactory, `quickgo_weaver.register(factory)` adds it as a provider.
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
