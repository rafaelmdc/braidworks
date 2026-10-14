# Alphafold source reference

Exact source outputs, coverage and implementation constraints. Start with
[the package overview](README.md) for setup and query entry points.

## Capabilities

| Capability | Input types | Output groups / expandable keys | Backends | Parameters |
|---|---|---|---|---|
| `describe_model` | `protein.uniprot.accession` | `model`, `confidence`, `full` | `api`, `archive` | — |
| `list_models` | `protein.uniprot.accession` | `models`; expands `structure.alphafold.model_id` | `api`, `archive` | — |
| `describe_prediction` | `structure.alphafold.model_id` | `model`, `confidence`, `full` | `api`, `archive` | — |

These are the current declared capabilities. Output groups select fields computed
together; expandable keys identify related entities you can follow. See
[the spec](weaver.spec.toml) for exact output fields and parameter defaults, or
`braidworks weavers` for the installed inventory. Backend declarations do not imply
that optional local data are already configured.

## Representative model and coverage

For the returned response, the backend prefers entry ID `AF-{accession}-F1`;
otherwise it selects the lexicographically lowest entry ID. This is a representative
selection rule, not a guarantee of full-sequence coverage or canonical isoform
identity. The records group describes only the selected entry (URLs, version and
confidence breakdown). Its `coverage` object retains the observed 1-based inclusive
UniProt start/end, sequence length, model length and fragment number. Status is
`full_sequence`, `partial` or `unknown` when evidence is missing. Partial models carry
a warning even on scalar-only requests. F1 can be the first overlapping fragment of
a long protein; it does not guarantee a complete model. `list_models` separately
lists entries observed by the selected API or archive backend; `describe_prediction`
retrieves one explicit model identity.

A valid UniProt accession can lack a model. Coverage depends on the provider’s
datasets and sequence exclusions; isoforms and fragments need separate inspection.
See the [AlphaFold DB FAQ](https://www.alphafold.ebi.ac.uk/faq) for current coverage.
HTTP 400/404 and a valid empty response produce `NO_MATCH`.

The API returns the current model version (`latestVersion`), which is exposed as
`structure.alphafold.version`. The same accession can yield different versions,
coordinates, confidence or available entries after a provider update. Selection is
deterministic for a fixed response, not a historical model-version pin.

## Develop
Run the commands from this package directory.

```bash
make verify                        # spec ↔ manifest, reachability, real fingerprints (--strict adds golden)
make test                          # conformance + contract + golden, fully offline
BRAIDWORKS_RUN_LIVE=1 make test    # also hit the live AlphaFold API (schema-drift detector)
```

Extend it: [CONTRIBUTING.md](https://github.com/rafaelmdc/braidworks/blob/main/weavers/alphafold_weaver/CONTRIBUTING.md) · build loop & boundaries: [AGENTS.md](https://github.com/rafaelmdc/braidworks/blob/main/AGENTS.md).

## Batch execution

The backend runs per-query lookups with at most four concurrent operations by
default, preserving one ordered result per input and per-input failures. Set
max_concurrency when constructing the API backend to lower the bound. This is a
concurrency limit, not an HTTP requests-per-second guarantee. Existing bulk
operations, where implemented, keep their batch endpoints.

## Source response and failure handling

Prediction responses must be lists of model objects with an entry identifier and correctly typed projected fields. An empty list remains a miss. A malformed response affects only its accession; null/blank inputs do not issue requests.

Expected HTTP, JSON-decoding and explicitly validated source-data failures are returned as failure values. Cancellation and unrelated programming exceptions propagate. Existing successful output keys are preserved; consumers should handle `ERROR` separately from biological absence. Unknown extra source fields are allowed.

## Construction and resource lifetime
For validated builders and client ownership, see
[shared configuration](../../docs/weaver-configuration.md).


## Confidence data references

Request `structure.alphafold.confidence` from `describe_model` to receive the
provider's PAE and per-residue pLDDT JSON URLs, model version and sequence coverage.
Missing source URLs remain `None`; lookup never downloads those files. pLDDT
is local confidence on a 0–100 scale; PAE measures predicted relative placement
error in angstroms. Neither is an experimental measurement. Existing representative
selection and outputs are unchanged.

## Explore API-observed models

`list_models` accepts `protein.uniprot.accession` and emits the full distinct,
ordered `structure.alphafold.model_id` fan set (`entryId@vN`). Its display records
are capped at ten; coverage counts the observed API entries only. The API does
not enumerate archive-only long-protein fragments.

`describe_prediction` consumes one of those version-qualified IDs and exposes the
same model/full/confidence groups as `describe_model`. It queries the source entry
and refuses a different returned version rather than silently upgrading a saved
identity. Existing accession-based `describe_model` keeps its representative choice.

### Archive-only long fragments and isoforms

The [provider's downloads documentation](https://alphafold.ebi.ac.uk/download)
places long-protein overlapping fragments in proteome archives, outside the ordinary
website/API inventory. Use an already acquired, **uncompressed outer TAR**:

```python
weaver = build_alphafold_weaver(
    archive_paths=["/data/UP000005640_9606_HUMAN_v6.tar"],
    max_archive_members=100_000,
    max_archive_header_bytes=64 * 1024 * 1024,
)
# Execute list_models / describe_prediction with backend="archive".
```

The backend seeks over compressed model bodies and reads only headers; it extracts
nothing and downloads nothing. It enumerates explicit `AF-<accession>-F<n>-model_v<v>`
identities, keeps versions distinct, and groups CIF/PDB members as artifact locators.
A canonical accession query includes observed isoform filenames; an isoform query
matches that isoform only. Full fan IDs remain separate from the ten-record display.
A capped scan warns; an unobserved model in an incomplete scan is an error. Completeness
refers only to supported model filenames in the supplied archives, never the global DB.

`describe_prediction` returns exact entry/version identity and archive/member/offset
locators. It does not invent web URLs, residue ranges or confidence values from a
filename. The original representative capability also works with this scoped metadata.
The archive fingerprint covers observed headers, configured limits and file state;
it is explicitly not a full coordinate checksum. File changes invalidate the instance
and require rebuilding its index. Duplicate competing artifacts are rejected.
Compressed outer archives are rejected to avoid an implicit full decompression pass.

A real 4096-byte HTTP range probe of the current human archive observed
`AF-A0A024R1R8-F1-model_v6.cif.gz`; the full 5.18 GB archive was not downloaded.
