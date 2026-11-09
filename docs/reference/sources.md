# Source catalogue

Every source package in this repository: what to use it for and what it needs before
it can answer. A source being listed means its capabilities are declared; it does not
mean every input will match, or that an unconfigured backend is ready. For the steps
to install and prepare sources, see [choose and set up sources](../how-to/choose-sources.md);
for why some sources need setup, [where the data comes from](../explanation/where-data-comes-from.md).

| Weaver | Use it for | Setup |
|---|---|---|
| [UniProt](../../weavers/uniprot_weaver/README.md) | Protein identity, sequence/annotations, identifier mapping | Keyless API. Pin organism for gene symbols; representative search is not all-match resolution. |
| [PDBe](../../weavers/pdbe_weaver/README.md) | Experimental structures, entities/assemblies/ligands, SIFTS mapping, coordinate links | Keyless API; residue mapping downloads bounded per-entry SIFTS data on request. |
| [AlphaFold](../../weavers/alphafold_weaver/README.md) | Predicted model metadata and archive inventories | Keyless API; optional header-only indexing of supplied uncompressed outer TAR archives. Predictions are not experimental structures. |
| [QuickGO](../../weavers/quickgo_weaver/README.md) | GO annotations/evidence, term details/hierarchy, reverse gene-product queries | Keyless API. Pagination budgets can limit coverage; inspect completeness warnings. |
| [Reactome](../../weavers/reactome_weaver/README.md) | Pathways, contained reactions, and provider evidence | Keyless API. Evidence records are source observations, not synthesized confidence scores. |
| [STRING](../../weavers/string_weaver/README.md) | Functional association networks | Keyless API. Species, score, and display limits are parameters; associations need not be physical interactions. |
| [NCBI](../../weavers/ncbi_weaver/README.md) | Taxonomy, genes, genomes, and related-entity queries | Keyless Datasets API by default; optional local taxonomy database. Backend capability coverage differs. |
| [BacDive](../../weavers/bacdive_weaver/README.md) | Strain phenotypes and culture-collection/genome cross-references | Keyless API. Taxid lookup describes a type-strain representative, not every isolate. |
| [Disbiome](../../weavers/disbiome_weaver/README.md) | Microbe–disease associations and reverse disease queries | Prepared local SQLite database required. Provider disease IDs and MedDRA codes have distinct identity rules. |
| [FAPROTAX](../../weavers/faprotax_weaver/README.md) | Taxonomy-based ecological functional groups | Bundled text, offline. Input is a lineage; inferred functions are not measured traits. |
| [GMrepo](../../weavers/gmrepo_weaver/README.md) | Microbial abundance, phenotype associations, runs/cohorts | Prepared local SQLite database. Sample profiles must be included for profile outputs; cohort filters describe retained data coverage. |
| [GTDB](../../weavers/gtdb_weaver/README.md) | Taxon placement and genome-card quality/history | Keyless API for supported name/genome queries; taxid crosswalk and tree placement need separate local data. |
| [MONDO](../../weavers/mondo_weaver/README.md) | Disease names, identifiers, ontology details, typed mappings | Prepared local SQLite database. Typed mappings require explicitly supplied release-matched SSSOM data. |
| [Wikidata](../../weavers/wikidata_weaver/README.md) | Taxon names and entity identifiers | Keyless SPARQL endpoint. Homonyms can pause for review; `expected_rank` refines disambiguation. |
| [Wikipedia](../../weavers/wikipedia_weaver/README.md) | Pageview-based attention signals | Keyless API uses trailing 12 whole months; optional local dumps cover one specified month. Windows are not interchangeable. |
| [AGORA](../../weavers/agora_weaver/README.md) | Metabolic reconstructions, reaction membership, and genome crosswalks | Bundled crosswalk; reaction outputs require a separate SBML/database build, potentially multi-GB. |
| [Example](../../weavers/example_weaver/README.md) | Learn how an adapter works | Bundled teaching CSV, offline. Register explicitly in Python; deliberately not auto-discovered. |

Each linked README gives the source's entry points and scientific scope, with exact
capability tables and coverage contracts. `braidworks weavers` lists the capabilities
and parameters of the packages installed in your environment; `braidworks doctor`
shows which are ready; the [key index](keys-index.md) shows the connections across
every source.

## Backends

| Setup column says | Meaning |
|---|---|
| Keyless API | A public web service; needs network access and no account. |
| Bundled | Data shipped inside the package; works offline. |
| Prepared local database | A database built from the provider's published files before first use (see [choose and set up sources](../how-to/choose-sources.md#set-up-a-source-that-needs-local-data)). |

Fixture builders (`build_<source>_fixture`) wrap tiny test datasets. They power
`braidworks demo` and the conformance tests and are not research reference data.

## Versions and attribution

Packages version independently and declare a minimum core version; check installed
package metadata (`braidworks weavers`) rather than a version number in a guide.
`braidworks references` lists the citation for each installed source, and every
result keeps the references of the sources it drew on (`result.cite()`). MIT covers
the software. Biological data keep their providers' licences, citation requirements
and terms.
