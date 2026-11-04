# wikidata_weaver

Resolve taxon names to Wikidata items, map NCBI taxids, or describe an exact QID with
language-aware labels. Homonyms can require review; rank refines disambiguation. English
Wikipedia titles remain separate from localized labels. Live use depends on the public SPARQL
and entity services.

- **Source:** https://www.wikidata.org/
- **License:** CC0-1.0
- **Cite:** Wikidata, the free knowledge base. https://www.wikidata.org/

## Capabilities

| Capability | Use it to |
|---|---|
| `resolve_taxon` | Resolve a taxon name with ambiguity review |
| `map_from_taxid` | Map an NCBI taxid to observed Wikidata identities |
| `describe_taxon` | Inspect an exact QID and requested language |

See [source reference](REFERENCE.md#capabilities) for exact inputs, output groups, backends and parameters,
or inspect the [spec](weaver.spec.toml).

## Run a query

The implemented keyless SPARQL backend resolves taxon scientific names to Wikidata
items, English Wikipedia titles, sitelink counts and vernacular names.

    braidworks run wikidata resolve_taxon --have organism.scientific_name="Ursus arctos"

Names shared across taxonomic codes can have several candidates. Routed execution
pauses on ambiguity by default. If the expected rank is known, refine the query:

    braidworks weave --have organism.scientific_name="Ursus arctos" --want wikidata.qid --param expected_rank=species

From Python, build_wikidata_weaver() needs no configuration. Offline fixture and
golden tests are implemented; live use depends on the public SPARQL endpoint.

```bash
make verify   # check the weaver still matches its spec
make test     # run conformance + contract + golden tests
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
