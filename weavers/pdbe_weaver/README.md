# pdbe_weaver

List the experimental PDB entries observed for a protein accession, then inspect individual
structures, chain mappings and residue evidence. UniProt can supply the accession from a protein
query. Display lists are capped; expandable identifiers retain the observed set. A mapping alone
does not establish full-sequence coverage or structure suitability.

- **Source:** https://www.ebi.ac.uk/pdbe · **License:** CC0-1.0 · **Cite:** https://doi.org/10.1093/nar/gkz990 — wwPDB / EMBL-EBI PDBe
- **Backend:** `api` (keyless) · **Discoverable as** `pdbe`

## Capabilities

| Capability | Use it to |
|---|---|
| `list_structures` | List observed PDB entries for a protein |
| `describe_structure` | Inspect a PDB entry |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

Once installed it is auto-discovered by the `braidworks` CLI:

```bash
braidworks run pdbe describe_structure --have pdb.id=1tup
braidworks weave --have protein.query=P04637 --want structure.pdb.ids   # routed via uniprot
# fan one protein out into each structure's detail:
braidworks weave --have protein.query=P04637 --want structure.pdb.title --expand all
```

From Python:

```python
from pdbe_weaver import build_pdbe_weaver

weaver = build_pdbe_weaver()  # zero-config
# In an app that wires a WeaverFactory, `pdbe_weaver.register(factory)` adds it as a provider.
```

Follow the [researcher lesson](../../docs/tutorials/protein-structures.md) for a complete exercise.

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
