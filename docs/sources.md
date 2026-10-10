# Choose data sources

Install the weavers for the fields you need, then prepare any required local data.
A weaver's presence in the catalogue means its capabilities are declared; it does
not mean every input will match or that an unconfigured backend is ready to run.

Public API backends need network access. Local backends use bundled data or a
separately acquired database/archive. Fixture builders contain tiny test datasets
and are not research reference data.

## Source catalogue

This checkout contains 17 weaver packages. Each linked README gives the source's
capabilities, filters, coverage rules, and citations. `braidworks weavers` lists only
the packages installed in your environment; the [key index](keys-index.md) shows
connections across the repository.

| Weaver | Use it for | Setup |
|---|---|---|
| [UniProt](../weavers/uniprot_weaver/README.md) | Protein identity, sequence/annotations, identifier mapping | Keyless API. Pin organism for gene symbols; representative search is not all-match resolution. |
| [PDBe](../weavers/pdbe_weaver/README.md) | Experimental structures, entities/assemblies/ligands, SIFTS mapping, coordinate links | Keyless API; residue mapping downloads bounded per-entry SIFTS data on request. |
| [AlphaFold](../weavers/alphafold_weaver/README.md) | Predicted model metadata and archive inventories | Keyless API; optional header-only indexing of supplied uncompressed outer TAR archives. Predictions are not experimental structures. |
| [QuickGO](../weavers/quickgo_weaver/README.md) | GO annotations/evidence, term details/hierarchy, reverse gene-product queries | Keyless API. Pagination budgets can limit coverage; inspect completeness warnings. |
| [Reactome](../weavers/reactome_weaver/README.md) | Pathways, contained reactions, and provider evidence | Keyless API. Evidence records are source observations, not synthesized confidence scores. |
| [STRING](../weavers/string_weaver/README.md) | Functional association networks | Keyless API. Species, score, and display limits are parameters; associations need not be physical interactions. |
| [NCBI](../weavers/ncbi_weaver/README.md) | Taxonomy, genes, genomes, and related-entity queries | Keyless Datasets API by default; optional local taxonomy database. Backend capability coverage differs. |
| [BacDive](../weavers/bacdive_weaver/README.md) | Strain phenotypes and culture-collection/genome cross-references | Keyless API. Taxid lookup describes a type-strain representative, not every isolate. |
| [Disbiome](../weavers/disbiome_weaver/README.md) | Microbe–disease associations and reverse disease queries | Prepared local SQLite database required. Provider disease IDs and MedDRA codes have distinct identity rules. |
| [FAPROTAX](../weavers/faprotax_weaver/README.md) | Taxonomy-based ecological functional groups | Bundled text, offline. Input is a lineage; inferred functions are not measured traits. |
| [GMrepo](../weavers/gmrepo_weaver/README.md) | Microbial abundance, phenotype associations, runs/cohorts | Prepared local SQLite database. Sample profiles must be included for profile outputs; cohort filters describe retained data coverage. |
| [GTDB](../weavers/gtdb_weaver/README.md) | Taxon placement and genome-card quality/history | Keyless API for supported name/genome queries; taxid crosswalk and tree placement need separate local data. |
| [MONDO](../weavers/mondo_weaver/README.md) | Disease names, identifiers, ontology details, typed mappings | Prepared local SQLite database. Typed mappings require explicitly supplied release-matched SSSOM data. |
| [Wikidata](../weavers/wikidata_weaver/README.md) | Taxon names and entity identifiers | Keyless SPARQL endpoint. Homonyms can pause for review; `expected_rank` refines disambiguation. |
| [Wikipedia](../weavers/wikipedia_weaver/README.md) | Pageview-based attention signals | Keyless API uses trailing 12 whole months; optional local dumps cover one specified month. Windows are not interchangeable. |
| [AGORA](../weavers/agora_weaver/README.md) | Metabolic reconstructions, reaction membership, and genome crosswalks | Bundled crosswalk; reaction outputs require a separate SBML/database build, potentially multi-GB. |
| [Example](../weavers/example_weaver/README.md) | Learn how an adapter works | Bundled teaching CSV, offline. Register explicitly in Python; deliberately not auto-discovered. |

## Prepare local-only sources

Install the selected package before running its setup function. For example, after
installing `disbiome_weaver`, save this as a script and run it in your environment:

```python
from disbiome_weaver.setup import ensure_disbiome_db

ensure_disbiome_db(auto=True)
```

`auto=True` authorizes network acquisition. Omit it when checking for an already
prepared database. GMrepo and MONDO provide equivalent helpers documented in their
package READMEs; acquire only the sources you need.

Default discovery reads the default cache location. If you choose a custom database
path, pass it to the Python configured builder too. See
[builder configuration](weaver-configuration.md).

For optional NCBI local setup, follow [database setup](database.md). Read the GTDB
and AGORA package READMEs before acquiring larger reference data. AGORA's bundled
reconstruction crosswalk works offline; reaction outputs require a separate SBML/database
build that can acquire a multi-GB archive. Its archive dependency may need a compiler.

## Versions and attribution

Packages version independently and declare a minimum core version. The workspace
resolves compatible local packages; check package metadata rather than relying on a
version number in this guide. Older workflows may need the
[ambiguity-policy migration](migrating-to-0.12.md).

`braidworks references` lists source references from installed weavers; query results
retain references for executed sources. MIT covers the software. Biological data keep
their providers' licenses, citation requirements, and terms.
