# Braidworks documentation

Braidworks connects lookups across biological data sources. Start with a small query,
choose the sources your analysis needs, then scale to a batch. The
[README](../README.md) introduces the tool and includes a first command.

| You want to… | Go to |
|---|---|
| Learn by working through a full example | [Tutorials](tutorials/) |
| Get a specific task done | [How-to guides](how-to/) |
| Look up exact options, fields and contracts | [Reference](reference/index.md) |
| Understand how and why it works | [Explanation](explanation/) |

## Learn through a tutorial

| Exercise | What you will produce |
|---|---|
| [Protein structures](tutorials/protein-structures.md) | A structure listing, related-entry inspection and batch export |
| [Microbial functions](tutorials/microbial-functions.md) | An ecological annotation with its supporting rule trace |
| [Disease–microbe associations](tutorials/disease-associations.md) | Observations with provider identity, sample context and publications |

## Complete a task

1. [Install Braidworks](how-to/install.md): choose packages and create a local environment.
2. [Run a query](how-to/run-queries.md): use the CLI, Python, or browser, then process a batch.
3. [Read the results](how-to/check-results.md): check coverage, review matches, and export your data.

For interactive work, [build and run a query in the browser](how-to/use-the-browser.md).

## Look up sources and interfaces

Use the [source catalogue](how-to/choose-sources.md), [key index](reference/keys-index.md),
[core contracts](reference/core-contracts.md) and [builder configuration](reference/weaver-configuration.md)
for exact capabilities, connections and construction rules. Command help provides
CLI option reference; source READMEs link their specs and interpretation notes.
The [reference index](reference/index.md) brings these lookup paths together,
including [result shapes](reference/results.md) and [storage contracts](reference/persistence.md).

## More tasks for your data

| Task | Guide |
|---|---|
| Choose sources and prepare local data | [Source catalogue](how-to/choose-sources.md) |
| Find input and output field names | `bw.find("pdb structures")` in Python, or the [key index](reference/keys-index.md) |
| Follow every related structure, pathway, or other entity | [Expansion and relationships](how-to/run-queries.md#follow-related-entities) |
| Reuse lookups and continue saved work | [Cache and saved runs](how-to/cache-and-resume.md) |
| Prepare the optional local NCBI taxonomy database | [NCBI database setup](how-to/set-up-ncbi-database.md) |
| Limit requests to upstream services | [HTTP request pacing](how-to/set-request-rates.md) |
| Inspect the source network offline | [Network view](network/braidworks-network.html), opened in a browser |

Exact command options are available through `braidworks --help`,
`braidworks weave --help`, and each subcommand's `--help`. Source-specific capabilities,
parameters, and interpretation notes live in the package READMEs linked from the
[source catalogue](how-to/choose-sources.md).

## Understand or extend Braidworks

For the overall model, start with [how Braidworks fits together](explanation/architecture.md).
For scientific interpretation, read [what a lookup result establishes](explanation/result-meaning.md).
The links below support understanding the framework and contributing to it.

| Task | Documentation |
|---|---|
| Understand planning, execution, and package boundaries | [Architecture](explanation/architecture.md) |
| Check framework contracts while implementing an adapter | [Core contracts](reference/core-contracts.md) |
| Configure builders and manage their resources | [Weaver configuration](reference/weaver-configuration.md) |
| Find code in the workspace | [Repository structure](reference/repo-structure.md) |
| Contribute a fix or new source | [Contributing](../CONTRIBUTING.md), [repository rules](../AGENTS.md), and [weaverkit](../weaverkit/README.md) |
| Implement a weaver's backend | [Implementation guide](how-to/implement-a-weaver.md) |
| Build and check release artifacts | [Release rehearsal](how-to/release.md) |
| Use the experimental distributed adapter | [braidworks-arq](../braidworks-arq/README.md) |

## Upgrade notes and project history

For documentation contributors, the [Diátaxis map](internal/audits/documentation-diataxis.md)
records current page roles, gaps and proposed edits; [writing conventions](reference/documentation-style.md)
explain how to preserve useful detail during a rewrite.

For older workflows, see [core 0.12 ambiguity changes](how-to/migrate-to-core-0.12.md) and
[core 0.13 batching and pacing changes](how-to/migrate-to-core-0.13.md).
[Current work](internal/NEXT.md) describes remaining project decisions.

[Roadmaps and original plans](internal/history.md), [audit records](internal/audits/README.md), and
[refactoring records](internal/refactoring/README.md) preserve design and validation history.
Their dates and completion notes matter; use the guides above for current behavior.
