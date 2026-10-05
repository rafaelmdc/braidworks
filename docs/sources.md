# Weaver setup catalogue

This catalogue covers all 17 weaver packages in this checkout. The shared-key
[index](keys-index.md) lists their current connections; braidworks weavers shows
capabilities and parameters for the packages actually installed in your environment.

Keyless HTTP sources require network access. A zero-config local-only builder can
be discoverable while its database is unconfigured; discovery does not grant
download consent. Fixture builders are for tests, not full biological datasets.

| Package | Setup and interpretation |
|---|---|
| [agora_weaver](../weavers/agora_weaver/README.md) | Bundled reconstruction crosswalk works offline. Reaction outputs need a separate consented SBML/database build; the archive is about 2.17 GB. build_agora_weaver(auto_setup=True) enables that build. Installing its archive dependency can require a compiler. |
| [alphafold_weaver](../weavers/alphafold_weaver/README.md) | Keyless HTTP API; zero-config builder. Predictions are model data, not experimental structures. |
| [bacdive_weaver](../weavers/bacdive_weaver/README.md) | Keyless HTTP API; zero-config builder. Returns a species type-strain representative, not an arbitrary isolate. |
| [disbiome_weaver](../weavers/disbiome_weaver/README.md) | Local SQLite required. Run ensure_disbiome_db(auto=True) once, or use build_disbiome_weaver_configured(db_path=...) for a prepared database. The default discovery builder never downloads it. |
| [example_weaver](../weavers/example_weaver/README.md) | Bundled teaching CSV; works offline. Deliberately has no discovery entry point. Register build_example_weaver() explicitly in Python. |
| [faprotax_weaver](../weavers/faprotax_weaver/README.md) | Bundled FAPROTAX text; works offline. Input is a lineage, not a species-name string. Keep the source attribution and embedded license. |
| [gmrepo_weaver](../weavers/gmrepo_weaver/README.md) | Local SQLite required. Run ensure_gmrepo_db(auto=True) once, or configure an existing db_path. Sample-profile outputs need profiles included in the build; see the package README. |
| [gtdb_weaver](../weavers/gtdb_weaver/README.md) | Keyless API supports scientific-name queries. Taxid crosswalk and tree placement need local data; build_gtdb_weaver(auto_setup=True) acquires the crosswalk, with separate tree-placement options. |
| [mondo_weaver](../weavers/mondo_weaver/README.md) | Local SQLite required. Run ensure_mondo_db(auto=True) once, or configure a prepared db_path. Names, MeSH IDs and MedDRA IDs have separate capabilities. |
| [ncbi_weaver](../weavers/ncbi_weaver/README.md) | Keyless Datasets API is usable by default. Local taxonomy is optional and requires a database; see database.md. API-only Python configuration uses enable_api=True. |
| [pdbe_weaver](../weavers/pdbe_weaver/README.md) | Keyless HTTP API; zero-config builder. List structures by accession, then describe a fanned pdb.id. |
| [quickgo_weaver](../weavers/quickgo_weaver/README.md) | Keyless HTTP API; zero-config builder. Term inventories are bounded by a page cap. Annotation detail retains evidence/qualifiers, and coverage metadata plus warnings report incomplete retrieval. |
| [reactome_weaver](../weavers/reactome_weaver/README.md) | Keyless HTTP API; zero-config builder. Lists pathway IDs and describes individual pathways. |
| [string_weaver](../weavers/string_weaver/README.md) | Keyless HTTP API; zero-config builder. Results are STRING functional associations; inspect parameters for species, score and display limits. |
| [uniprot_weaver](../weavers/uniprot_weaver/README.md) | Keyless HTTP API; zero-config builder. Pin organism for gene symbols. Symbol lookup selects a deterministic representative; an accession is the most specific input. |
| [wikidata_weaver](../weavers/wikidata_weaver/README.md) | Keyless SPARQL endpoint; zero-config builder. Homonyms can pause for review. expected_rank refines taxon disambiguation. |
| [wikipedia_weaver](../weavers/wikipedia_weaver/README.md) | Keyless API sums the trailing 12 whole months of English Wikipedia pageviews. Optional local dumps cover one explicit month, so the two backend totals have different windows. |

## Prepare local-only sources

Build a database explicitly before using its default CLI-discovered backend. These
commands authorize a real network acquisition; run only for sources you need:

    from disbiome_weaver.setup import ensure_disbiome_db
    from gmrepo_weaver.setup import ensure_gmrepo_db
    from mondo_weaver.setup import ensure_mondo_db

    ensure_disbiome_db(auto=True)
    ensure_gmrepo_db(auto=True)
    ensure_mondo_db(auto=True)

Run the selected call from a script in the environment where that weaver is
installed. Omit auto=True when checking for an already prepared database. Each
setup function accepts an explicit database path; a custom path must also be passed
to the Python configured builder. CLI discovery reads the default cache location.

For NCBI local setup, see [database.md](database.md). For GTDB trees and AGORA
reactions, read their package README before enabling the larger downloads.

## Versions and citations

Packages version independently. Metadata declares a core floor; the full workspace
currently uses core 0.12.0 and its default review pause. See the
[migration guide](migrating-to-0.12.md) before upgrading an older workflow.

braidworks references prints source references from installed weavers. Braid results
carry references for executed sources. MIT applies to software; each source keeps
its own provenance license, attribution and data terms.
