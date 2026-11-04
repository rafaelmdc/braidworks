# Weaver construction and HTTP resource lifetime

Builder/provider options are validated. Unknown names raise
BackendConfigurationError without echoing their values. Zero-argument construction
inspects available sources without starting a download. Local setup requires
explicit consent (auto_setup or BRAIDWORKS_AUTO_DOWNLOAD) or a package’s documented
interactive prompt. AGORA’s configured wrapper never forces consent; Disbiome
implements no terminal prompt. Per-query --param settings remain distinct from
builder options and are declared in each capability spec.

## Provider configuration

```python
import asyncio
from braidworks.core import WeaverFactory
from uniprot_weaver import register

async def main():
    factory = WeaverFactory()
    register(factory)
    async with factory.build("uniprot", {"max_concurrency": 2}) as weaver:
        # Execute batches here; leaving the context closes owned HTTP clients.
        print(weaver.MANIFEST.weaver_id)

asyncio.run(main())
```

## Ownership rules

- Backends lazily create and own a client when none is supplied. `aclose()` is
  idempotent, closes an initialized owned client once, and does not create a client.
- Injected clients are borrowed. Their actual base_url controls relative requests
  and source fingerprint; builder base_url configures owned clients only. Supply
  an absolute base_url when constructing the injected client. The caller closes it.
- HTTP backend closure is terminal; construct a new backend to run more requests.
  Finish active batches before closing. Cancellation is propagated rather than
  swallowed by cleanup. Shared dispatch tries all distinct adapters on normal close
  failures and reports an ExceptionGroup. Resource-free adapters need no close hook.
- NCBI api_key with an injected client must match that client’s api-key header;
  otherwise construction fails clearly. Credentials never appear in fingerprints.
- Fingerprints identify effective endpoints and result-affecting source scope,
  not a frozen remote dataset. Monthly Wikidata freshness is a cache descriptor,
  not evidence that provider content stays fixed for that month.

GTDB and Wikipedia per-name/title APIs use at most four workers by default,
deduplicate inputs per batch and default to five requests/second through the
existing pacing seam. Explicit request-pacing policies can override that default.
Request count, concurrency and per-query biological parameters are separate knobs.

## Supported public builders

The signatures below list source-local construction options; **_config/**_ignore
only captures unsupported names so they receive a clear configuration error.
Local Disbiome/GMrepo/MONDO discovery builders forward nonempty config to their
configured builder (listed immediately after the discovery signature).

Configured helpers may be defined in `<package>.factory` rather than re-exported
from `<package>`. Import from that module when needed. Signatures are a snapshot of
the public functions in this checkout; consult their source when extending a builder.

### agora_weaver

```python
build_agora_weaver(*, db_path: 'str | Path | None' = None, auto_setup: 'bool' = False, refresh: 'bool' = False, sbml_cache_dir: 'str | Path | None' = None, auto_download_models: 'bool' = False, model_download_base_url: 'str' = 'https://vmh.life/api/getMicrobeReconstructions?version=agora2_2.01&format=sbml&id=', **_config: 'Any') -> 'BaseWeaver'
build_agora_weaver_configured(**config: 'Any') -> 'BaseWeaver'
```

### alphafold_weaver

```python
build_alphafold_weaver(*, base_url: 'str' = 'https://alphafold.ebi.ac.uk', client: 'httpx.AsyncClient | None' = None, max_concurrency: 'int' = 4, archive_paths: 'list[str] | None' = None, max_archive_members: 'int' = 100000, max_archive_header_bytes: 'int' = 67108864, **_config: 'Any') -> 'BaseWeaver'
```

### bacdive_weaver

```python
build_bacdive_weaver(*, base_url: 'str' = 'https://api.bacdive.dsmz.de/v2', client: 'httpx.AsyncClient | None' = None, max_strains_scanned: 'int' = 1000, max_concurrency: 'int' = 4, **_config: 'Any') -> 'BaseWeaver'
build_bacdive_weaver_configured(*, base_url: 'str' = 'https://api.bacdive.dsmz.de/v2', client: 'httpx.AsyncClient | None' = None, max_strains_scanned: 'int' = 1000, max_concurrency: 'int' = 4, **_config: 'Any') -> 'BaseWeaver'
```

### disbiome_weaver

```python
build_disbiome_weaver(**config: 'Any') -> 'BaseWeaver'
build_disbiome_weaver_configured(*, db_path: 'str | Path | None' = None, auto_setup: 'bool' = False, refresh: 'bool' = False, progress: 'ProgressCallback | None' = None, **_config: 'Any') -> 'BaseWeaver'
```

### example_weaver

```python
build_example_weaver(**config: 'Any') -> 'BaseWeaver'
```

### faprotax_weaver

```python
build_faprotax_weaver(**_config: 'Any') -> 'BaseWeaver'
```

### gmrepo_weaver

```python
build_gmrepo_weaver(**config: 'Any') -> 'BaseWeaver'
build_gmrepo_weaver_configured(*, db_path: 'str | Path | None' = None, auto_setup: 'bool' = False, refresh: 'bool' = False, profile_phenotypes: 'list[str] | None' = None, profile_max_runs: 'int' = 200, profile_filters: 'dict[str, str | int] | None' = None, acquisition_policy: 'AcquisitionPolicy | None' = None, **_config: 'Any') -> 'BaseWeaver'
```

### gtdb_weaver

```python
build_gtdb_weaver(*, db_path: 'str | Path | None' = None, auto_setup: 'bool' = False, refresh: 'bool' = False, release: 'str | None' = None, enable_tree_placement: 'bool' = False, tree_paths: 'list[str | Path] | None' = None, enable_api: 'bool' = False, api_base_url: 'str | None' = None, api_client: 'httpx.AsyncClient | None' = None, api_max_concurrency: 'int' = 4, **_config: 'Any') -> 'BaseWeaver'
build_gtdb_weaver_configured(**config: 'Any') -> 'BaseWeaver'
```

### mondo_weaver

```python
build_mondo_weaver(**config: 'Any') -> 'BaseWeaver'
build_mondo_weaver_configured(*, db_path: 'str | Path | None' = None, auto_setup: 'bool' = False, refresh: 'bool' = False, expected_version: 'str | None' = None, mapping_path: 'str | Path | None' = None, mapping_release: 'str | None' = None, **_config: 'Any') -> 'BaseWeaver'
```

### ncbi_weaver

```python
build_ncbi_weaver(*, db_path: 'str | Path | None' = None, cache_db_path: 'str | Path | None' = None, auto_setup: 'bool' = False, refresh: 'bool' = False, enable_api: 'bool' = False, api_base_url: 'str' = 'https://api.ncbi.nlm.nih.gov/datasets/v2', api_key: 'str | None' = None, api_client: 'httpx.AsyncClient | None' = None, allow_fuzzy: 'bool' = True, api_max_concurrency: 'int' = 4, api_max_report_pages: 'int' = 1000, **_config: 'Any') -> 'NCBITaxonWeaver'
```

### pdbe_weaver

```python
build_pdbe_weaver(*, base_url: 'str' = 'https://www.ebi.ac.uk/pdbe/api', client: 'httpx.AsyncClient | None' = None, limit: 'int' = 25, **_config: 'Any') -> 'BaseWeaver'
```

### quickgo_weaver

```python
build_quickgo_weaver(*, base_url: 'str' = 'https://www.ebi.ac.uk/QuickGO/services', client: 'httpx.AsyncClient | None' = None, max_pages: 'int' = 10, **_config: 'Any') -> 'BaseWeaver'
```

### reactome_weaver

```python
build_reactome_weaver(*, base_url: 'str' = 'https://reactome.org/ContentService', client: 'httpx.AsyncClient | None' = None, limit: 'int' = 30, max_concurrency: 'int' = 4, **_config: 'Any') -> 'BaseWeaver'
```

### string_weaver

```python
build_string_weaver(*, base_url: 'str' = 'https://version-12-5.string-db.org/api', client: 'httpx.AsyncClient | None' = None, limit: 'int' = 25, **_config: 'Any') -> 'BaseWeaver'
```

### uniprot_weaver

```python
build_uniprot_weaver(*, base_url: 'str' = 'https://rest.uniprot.org', client: 'httpx.AsyncClient | None' = None, max_concurrency: 'int' = 4, **_config: 'Any') -> 'BaseWeaver'
```

### wikidata_weaver

```python
build_wikidata_weaver(*, base_url: 'str' = 'https://query.wikidata.org', client: 'httpx.AsyncClient | None' = None, entity_api_url: 'str' = 'https://www.wikidata.org/w/api.php', **_config: 'Any') -> 'BaseWeaver'
```

### wikipedia_weaver

```python
build_wikipedia_weaver(*, db_path: 'str | Path | None' = None, dump_path: 'str | Path | None' = None, year: 'int | None' = None, month: 'int | None' = None, auto_setup: 'bool' = False, refresh: 'bool' = False, enable_api: 'bool' = False, api_client: 'httpx.AsyncClient | None' = None, api_base_url: 'str | None' = None, api_months: 'int' = 12, api_end_month: 'str | None' = None, api_agent: 'str' = 'all-agents', api_max_concurrency: 'int' = 4, **_ignore: 'Any') -> 'BaseWeaver'
```

GTDB tree/release/refresh settings select the local setup path; endpoint/client
settings select API. Its configured wrapper requires an explicit source selection.
NCBI key/endpoint/fuzzy/page-budget settings select API even when enable_api is
omitted. Wikipedia exposes separate api_* options for its live scope; local dump
scope remains year/month/dump_path. Source-specific README examples describe
capabilities and required local artifacts.
