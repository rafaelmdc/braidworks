# Where the data comes from

Every value Braidworks returns was read from somewhere: a provider's web service, a
database built on your machine from the provider's published files, or a file shipped
inside a source package. Which one it was affects what you need before a lookup works,
how fresh the answer is, and what you can say about reproducing it. This page explains
those differences. For the steps, see [choose and set up sources](../how-to/choose-sources.md);
for each source's requirements, the [source catalogue](../reference/sources.md).

## Three kinds of backend

A source answers through one or more *backends*:

- **Web API.** UniProt, PDBe, Reactome and most other sources call the provider's
  public service when you query. Nothing is installed in advance and no account is
  needed, but each lookup needs the network, takes the time the provider takes, and
  returns whatever the provider holds today.
- **Local database.** Disbiome, GMrepo and MONDO (and optionally NCBI Taxonomy, GTDB
  and AGORA) read a SQLite database built once from the provider's published files.
  Lookups are fast and work offline afterwards, and the answer stays the same until
  you rebuild. The build is a separate, explicit step because it downloads data and
  takes disk space.
- **Bundled data.** FAPROTAX's rule table and AGORA's crosswalk ship inside the
  package. They need no setup and no network, and change only when the package does.

A source can offer more than one. NCBI answers names from the Datasets web API by
default and from a local taxonomy database when one is set up; the backend policy
(`--policy`, or **Local data or web APIs** in the browser) chooses which to try first.
[How routes are planned](how-routes-are-planned.md#what-the-backend-setting-changes)
explains how that choice interacts with routing.

## Why some sources need setup first

A provider that offers no query service, or whose service is too slow or limited for
batches, can only be used through a local copy. Braidworks never downloads a database
behind your back: building one is an action you take (`ensure_disbiome_db(auto=True)`,
`ncbi-weaver ensure`), because it costs bandwidth and disk and decides which release
your answers come from.

Until a source is set up it stays declared, so routes through it are still planned.
`braidworks doctor` shows it as needing setup. A query that reaches it returns the row
with the fields that other sources answered; the missing field's `why_missing` says the
source is not set up. That keeps one unprepared source from hiding everything else, and
keeps the gap visible instead of turning it into an empty value that looks like an
answer.

## Freshness and reproducibility

Web answers are current, so they drift. A rerun next month can return more PDB
structures or different pathway names, because the provider changed, not because the
query did. Local databases hold still until you rebuild them, so they suit an analysis
you need to repeat exactly, as long as you keep the database or record when it was
built.

Braidworks records enough to tell the two apart. Each source reports a fingerprint of
the data it read (a release tag, build date or checksum). The lookup cache keys on it,
so a rebuilt database does not return stale cached answers, and a run archive records
each source's fingerprint alongside its observations. [What a lookup result establishes](result-meaning.md#saved-observations-and-reproducibility)
covers what an archive does and does not freeze.

## Sample data is not reference data

Every source can also be built from a tiny fixture: canned API responses or a handful
of rows. The conformance tests use these, and so does `braidworks demo`, which needs
no network. Fixture values are real in shape but deliberately small (a few PDB
structures for TP53 rather than hundreds), so they demonstrate the tool, not the
biology. Do not cite them; run the same query against the live sources instead.

## Licences and citation

Wherever the data came from, it stays the provider's. Each source declares its licence
and preferred citation, and every result carries the references of the sources that
contributed to it, so the citation list matches what you actually used. The software's
MIT licence does not cover the data.
