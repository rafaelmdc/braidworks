# Choose and set up data sources

Install the sources your fields need, prepare any that read local data, and check
that each one is ready. The [source catalogue](../reference/sources.md) lists every
source with what it is for and what it needs.

## Check what is installed and ready

```bash
braidworks doctor
```

From a checkout, prefix commands with `uv run`. `doctor` lists each installed source as
ready, partly ready (for example, ready through its web API but not its local data) or
needing setup, and names sources in the repository that are not installed. A query
whose field comes from a source that is not set up still returns the row; its
`why_missing` column says "*source* is not set up on this machine".

## Install the sources you need

[Install everything](install.md#install-everything) unless you need a small
environment; [install only some sources](install.md#install-only-some-sources)
explains how to name them. Not sure which source provides a field? [Find a field](find-a-field.md).

## Set up a source that needs local data

Disbiome, GMrepo and MONDO read a prepared local database. Each package has a setup
helper that builds it from the provider's published files. For Disbiome, save this
as a script and run it in your environment:

```python
from disbiome_weaver.setup import ensure_disbiome_db

ensure_disbiome_db(auto=True)
```

`auto=True` authorizes the download; omit it to check for an already prepared
database. GMrepo and MONDO provide equivalent helpers, documented in their package
READMEs. Acquire only the sources you need.

The database goes to the default cache location, where ordinary discovery finds it.
If you choose a custom path, pass the same path to the source's configured builder in
Python; see [builder configuration](../reference/weaver-configuration.md).

For the optional local NCBI taxonomy, follow [NCBI database setup](set-up-ncbi-database.md).
Read the GTDB and AGORA READMEs before acquiring their larger reference data: AGORA's
reaction outputs need a separate build that can download a multi-GB archive, and its
archive dependency may need a C compiler.

## Check the setup worked

Run `braidworks doctor` again: the source should now show as ready. Then run one
query that uses it and check that `why_missing` is empty.

## Cite the sources you used

`braidworks references` prints the citation for every installed source, and each
result keeps the references of the sources it drew on (`result.cite()` in Python, the
**Sources to cite** panel in the browser). Data keep their providers' licences and
terms; see [versions and attribution](../reference/sources.md#versions-and-attribution).
