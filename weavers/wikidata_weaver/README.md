# wikidata_weaver

Wikidata taxon names (scientific name -> QID, vernacular names, enwiki title) weaver for Braidworks.

- **Source:** https://www.wikidata.org/
- **License:** CC0-1.0
- **Cite:** Wikidata, the free knowledge base. https://www.wikidata.org/

## Use it

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

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import wikidata_weaver

factory = WeaverFactory()
wikidata_weaver.register(factory)        # makes "wikidata" buildable
```

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/wikidata_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.


## Source response and failure handling

SPARQL envelopes and bindings are validated before accumulation. Query/service HTTP 400/404 is an error, never evidence of taxon absence; it is not retried. Taxon absence is a valid empty bindings list. Query literals escape quotes, backslashes and control characters. Each chunk has at most four attempts within a 90-second elapsed budget (including request time and waits); Retry-After seconds/HTTP dates are honored when they fit, otherwise the chunk fails without retrying early. Errors retain the final reason. expected_rank remains a homonym disambiguator: it chooses a uniquely matching rank only among multiple items and does not reject a single item with another rank.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.
