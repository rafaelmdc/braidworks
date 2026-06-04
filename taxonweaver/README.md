# taxonweaver

NCBI taxonomy weaver for Braidworks. Wraps the local SQLite taxonomy resolver
(`taxonomy_resolver`, migrated from taxonbridge) and the NCBI Datasets v2 REST
API behind a single `NCBITaxonWeaver` with two interchangeable backends
(`local`, `api`).

Both backends normalize to a neutral `TaxonMatch` intermediate, then a single
mapper produces `WeaveResult` strands — so the two backends emit identical strand
shapes even though their matching can differ.
