# disbiome_weaver

Retrieve observed microbe–disease associations in either direction, then inspect disease
identity, sample context and publication evidence. Build a local SQLite database from the source
tables before querying. Counts describe experiments, and associations do not establish
causation. Provider disease IDs and MedDRA codes are distinct.

- **Source:** https://disbiome.ugent.be (keyless JSON API on port 8080) · **License:** Open · **Cite:** https://doi.org/10.1186/s12866-018-1197-5 — Janssens et al., 2018
- **Backend:** `local` (a small SQLite built from the API; see below) · **Discoverable as** `disbiome`

## Capabilities

| Capability | Use it to |
|---|---|
| `disbiome.list_diseases` | List disease observations for an exact taxid |
| `disbiome.list_taxa` | List observed taxa for a disease ID or MedDRA code |
| `disbiome.describe_disease` | Inspect an exact provider disease ID |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

Build the DB once, then it chains straight off `ncbi_weaver`
(`organism.name → ncbi.taxon.id → microbe.disease.*`):

```python
from disbiome_weaver import build_disbiome_weaver_configured

# Acquires the source tables on first use with explicit auto_setup consent (or
# BRAIDWORKS_AUTO_DOWNLOAD=1); no terminal prompt is implemented.
# Override the database location with db_path=.
weaver = build_disbiome_weaver_configured(auto_setup=True)
# In an app that wires a WeaverFactory, `disbiome_weaver.register(factory)` adds it as a provider.
```

For CLI discovery, first build the **default** cache with
`ensure_disbiome_db(auto=True)` from `disbiome_weaver.setup`. The default discovery
builder only inspects that cache; it does not build it. Then run:

```bash
braidworks run disbiome disbiome.list_diseases --have ncbi.taxon.id=816
```

Follow the [researcher lesson](../../docs/tutorials/disease-associations.md) for a complete exercise.

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
