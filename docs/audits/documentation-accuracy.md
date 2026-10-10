# Documentation accuracy after the feature updates

Date: 2026-10-10. Tracker: [#300](https://github.com/rafaelmdc/braidworks/issues/300).
This follows the [readability pass](documentation-readability.md): active operating
instructions and capability summaries are reconciled with the current checkout.

## Confirmed mismatches

| Area | Incorrect or misleading guidance | Correction and source of truth |
|---|---|---|
| Weaver summaries | Tables omitted 30 declared capabilities, counting packages that had no capability table; some existing rows missed new groups/parameters | All 17 README summaries now cover 58 unique runtime capabilities and their input types, groups, set keys, backends, and parameters; compared with specs and `vocab.build_manifest` |
| MONDO | SSSOM ingestion called deferred; group notes imply schema 3 remains usable | Optional release-matched ingestion is implemented; current setup validates schema 5; old group-only migration note explicitly historical |
| AlphaFold | Only API backend advertised; model listing called a proposal | API/archive inventory and explicit prediction lookup are implemented, retaining source-scoped coverage |
| NCBI | Local descendants both implemented and declared API-only; all backends called interchangeable; zero-argument discovery treated as configured selection | Taxonomy/descendants support both, history local-only, gene/genome API-only; discovery can include unconfigured local data |
| AGORA | Claimed it consumes only taxids | Capabilities also consume reconstruction IDs, genome accessions, and reaction IDs; model membership is not measured metabolic activity |
| Disbiome | Called terminal and reverse disease lookup a future extension | `disbiome.list_taxa` and provider-disease description are implemented; identity distinctions retained |
| GTDB | All API coverage described as name-only; genome quality/history called future work | API taxonomy is name-based; separate exact-accession `describe_genome` provides observed card/quality/history |
| Registration | 7 READMEs require factory registration for routability | CLI discovery and direct `BraidRegistry` registration work; `WeaverFactory` is optional construction support |
| Scaffolded guidance | Generator would recreate the same registration claim and mandatory factory worklist | Updated generated README/provider explanation and implementation worklist, plus affected existing worklists |
| Request pacing | General guide says pacing is off unless configured | Source defaults: BacDive 2/s, STRING 1/s, NCBI/GTDB/Wikipedia 5/s; executor budget → explicit environment rule → local source default |
| Distributed pacing | Local/default vs cluster scope unclear; weave-step described as pure despite HTTP reads | Worker budget callback requires explicit matching rules for Redis pacing; cache identity does not make a source read pure |
| Toolkit README | Toolkit called stdlib-only despite depending on core; storage link points to NCBI setup | Clarified dependency-free TOML parser, current browser install path, and dedicated persistence reference |
| Generated catalogue | Scratch spec appears as a duplicate example; package backends shown for capability-scoped operations | Generator skips hidden scratch directories and respects capability backend overrides; regenerated indexes now contain 58 unique rows |

The catalogue fix is a small toolkit behavior change, not just a hand-edited artifact.
Two regression checks cover capability-scoped backend export and hidden scratch
specs. Toolkit version is patch-bumped to 0.6.20 and the lockfile matches. No weaver
runtime, manifest, source dataset, or scientific interpretation algorithm changed.

## Capability-summary coverage

“Missing” means absent from the prior summary table, not necessarily absent from all
prose. Several implemented features were appended later in the same README, leaving
the front-door inventory stale.

| Package | Current capabilities | Missing from old summary table |
|---|---:|---|
| `agora_weaver` | 6 | `describe_metabolic_reconstruction`, `describe_reaction`, `describe_reconstruction`, `list_genomes`, `list_reactions`, `list_reconstructions` |
| `alphafold_weaver` | 3 | `describe_prediction`, `list_models` |
| `bacdive_weaver` | 5 | `describe_strain`, `list_strains`, `map_from_strain`, `map_to_strain` |
| `disbiome_weaver` | 3 | `disbiome.describe_disease`, `disbiome.list_taxa` |
| `example_weaver` | 1 | — |
| `faprotax_weaver` | 1 | `describe_ecology` |
| `gmrepo_weaver` | 5 | `gmrepo.describe_run`, `gmrepo.list_phenotypes`, `gmrepo.list_runs` |
| `gtdb_weaver` | 3 | `describe_genome`, `describe_gtdb_taxonomy`, `describe_gtdb_tree_placement` |
| `mondo_weaver` | 4 | `describe_disease` |
| `ncbi_weaver` | 9 | `ncbi.describe_taxon_history` |
| `pdbe_weaver` | 2 | — |
| `quickgo_weaver` | 3 | `list_gene_products` |
| `reactome_weaver` | 4 | `describe_reaction`, `list_reactions` |
| `string_weaver` | 1 | — |
| `uniprot_weaver` | 4 | — |
| `wikidata_weaver` | 3 | `describe_taxon`, `map_from_taxid`, `resolve_taxon` |
| `wikipedia_weaver` | 1 | `describe_pageviews` |

The former generated count of 59 included `.audit-local/example-scaffold-baseline`.
That file is a local audit artifact, not another source or capability. Historical
acceptance reports retain their original generated counts; current catalogues use 58.

## Verification and remaining limits

- All 58 summary rows agree with runtime inputs, groups/set outputs, backends, and
  parameter names; specs agree with runtime declarations for these fields.
- All 61 executable `braidworks` lines found in the active root guides and package
  READMEs parse against the current CLI. Direct-call capabilities, requested output
  fields, and parameter names exist. This is structural validation, not a live run
  of every scientific example.
- The regenerated catalogue has 58 unique weaver/capability pairs and its backend
  cells match runtime capability declarations.
- All 1,050 local links/anchors across 206 Markdown files and whitespace checks pass.
- Workspace lint passes. The full workspace suite passes: 2,192 pytest tests,
  75 skipped live/optional tests, and five release-tool unit tests.
- The toolkit wheel and source archive build successfully; the wheel contains the
  corrected catalogue and scaffold generators.

Historical plans retain their dated statements under explicit history notices. This
pass checks active guidance, capability summaries, and prominent operational claims;
it does not certify every provider fact, historical sample, diagram, or paragraph.
No new provider quotas, licenses, or biological conclusions are inferred. Multi-GB
acquisition examples were not run. The joint review still needs three researcher
workflows, coverage interpretation, and navigation testing.
