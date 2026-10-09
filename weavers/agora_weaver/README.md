# agora_weaver

AGORA2 metabolic reconstructions (NCBI taxid -> reconstruction + reaction repertoire) weaver for Braidworks.

- **Source:** [Virtual Metabolic Human (VMH)](https://www.vmh.life) — AGORA2 (Heinken et al., *Nat Biotechnol* 2023)
- **License:** **CC BY-NC 4.0** ⚠️ — the VMH/AGORA2 *data* is **NonCommercial**. Fine for
  research/academic use; commercial use needs permission from the VMH authors. (The AGORA2
  *pipeline code* on GitHub is MIT, but that does not relax the data terms.)
- **Attribution:** AGORA2 / Virtual Metabolic Human (VMH), Heinken et al.
- **Cite:** https://doi.org/10.1038/s41587-022-01628-0

Maps an organism (by **NCBI taxid**) to its AGORA2 genome-scale metabolic
reconstruction(s) and, on request, the **reaction repertoire** of those models — the
substrate for metabolic complementarity/competition analysis. Consumes only `ncbi.taxon.id`
(name→taxid is `ncbi_weaver`'s job; the braider chains them).

## Outputs (grouped)

- **`core`** → `microbe.metabolism.reconstruction`: a list of `{reconstruction_id, gcf_id}`
  (the AGORA2 model and the RefSeq genome it was built from). Served from a **bundled**
  crosswalk (AGORA2 Supplementary Table S1) — **offline, all 7,302 strains, no download.**
- **`reactions`** → `microbe.metabolism.reactions`: the per-model reaction repertoire, a
  list of `{reconstruction_id, abbreviation, subsystem, ec, kegg, rhea}` (EC/KEGG/Rhea from
  the VMH reaction crosswalk — so this also acts as an **intermediate** into the molecular
  hub). Needs the reaction DB built by `ensure_agora_db` from the AGORA2 SBML archive
  (~2.17 GB, consent-gated); absent it, `core` still answers.

- **`model`** → `microbe.metabolism.sbml`: reconstruction ID, cached SBML path
  and source URL per model. Use `sbml_cache_dir` and explicitly enable
  `auto_download_models` to permit missing-model acquisition. Requested uncached
  models without consent are errors; they are not silently omitted.

```python
import agora_weaver

# core only (offline, no download):
weaver = agora_weaver.build_agora_weaver()

# also build the reaction repertoire DB (downloads the 2.17 GB SBML archive):
weaver = agora_weaver.build_agora_weaver(auto_setup=True)
```

```bash
make verify   # check the weaver still matches its spec
make test     # conformance + contract + golden tests (offline)
```

## Registering this weaver

A weaver is only reachable to the braider once its provider is registered in the
application's `WeaverFactory`. Wherever you assemble the factory:

```python
from braidworks.core import WeaverFactory
import agora_weaver

factory = WeaverFactory()
agora_weaver.register(factory)        # makes "agora" buildable
```

## Installation and documentation

Install this package together with a compatible core in a virtual environment.
See the [installation guide](https://github.com/rafaelmdc/braidworks/blob/main/docs/installation.md),
[source setup catalogue](https://github.com/rafaelmdc/braidworks/blob/main/docs/sources.md)
and [documentation index](https://github.com/rafaelmdc/braidworks/blob/main/docs/index.md).
Current release instructions use this checkout or built wheels; package-index
availability is not assumed.

## Software license

This package's software is licensed under [MIT](https://github.com/rafaelmdc/braidworks/blob/main/weavers/agora_weaver/LICENSE). Upstream biological data,
bundled source samples and provider content retain their separately declared source
licenses. The source license in a weaver manifest describes its data, not this code.

## Safe local database rebuilds

Direct builders and acquisition builds stage a fresh database beside the target,
validate its query schema and publish it atomically under the existing build lock.
Successful rebuilds remove rows from older datasets; failed input, validation or
publication leaves the original database unchanged. Allow space for both databases
and close writable target connections before replacement. Keep application-owned
tables in a separate database. Explicit local builds do not enforce the large
download disk margin used by consent-gated acquisition.

`build_reaction_db()` records the SBML content hash and the annotation row count,
SHA-256 and source. Optional `annotation_source=` and `sbml_source=` identify source
URLs; without them, metadata labels annotations caller-supplied and records the
local archive path. The annotation digest covers ordered JSON rows, not raw HTTP
bytes; it provides reproducibility evidence rather than a canonical dataset ID.
The XML parser releases processed elements, including nonreaction data.

## Resource and model coverage

Core-only crosswalk queries work offline. Requesting reactions without a reaction
database, or an unavailable SBML model without download consent, returns `ERROR`;
failed results claim no completed output groups. Partial SBML availability also
fails the requested model group rather than silently dropping reconstructions.

Reaction database schema 2 persists every processed/skipped XML model, its source
member, distinct reaction count and parse error. A processed model with zero
reactions is a known empty repertoire; a skipped or unacquired model is unavailable.
Existing databases without this manifest must be rebuilt before serving reactions.

## Bounded local work (0.2.5)

The bundled crosswalk is retained as immutable tuples; public lookups return
detached dictionaries and lists. Reaction lookup deduplicates model IDs and uses
two SQL queries per chunk of at most 250 models. Processed empty models remain
valid empty repertoires; skipped or missing coverage remains an error.

The configured wrapper preserves `auto_setup=False`; its name does not grant
download consent. Existing databases can be supplied without enabling downloads.

## Construction and resource lifetime

Supported builder options are explicit; unknown options raise
`BackendConfigurationError`. Empty construction remains safe for discovery.
See [configuration and lifetime](../../docs/weaver-configuration.md) for provider
configuration, source selection and owned/borrowed HTTP clients. Use
`async with weaver:` or `await weaver.aclose()` after requests finish.
