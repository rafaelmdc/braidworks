# Braidworks documentation

Braidworks connects lookups across biological data sources. Start with a small query,
choose the sources your analysis needs, then scale to a batch. The
[README](../README.md) introduces the tool and includes a first command.

| You want to… | Go to |
|---|---|
| Learn by working through a full example | [Tutorials](tutorials/index.md) |
| Get a specific task done | [How-to guides](how-to/index.md) |
| Look up exact options, fields and contracts | [Reference](reference/index.md) |
| Understand how and why it works | [Explanation](explanation/index.md) |

## Learn through a tutorial

| Exercise | What you will produce |
|---|---|
| [First query in the browser](tutorials/first-query-in-the-browser.md) | Names, structures and pathways for two genes, with the route that answered and a CSV, without code |
| [First analysis in Python](tutorials/first-analysis-in-python.md) | Names, GO terms and structures for two genes, as a pandas table with citations |
| [Getting-started notebook](../notebooks/getting-started.ipynb) | Install, find fields, look up, review a match and export, in Colab or Jupyter (installs from PyPI, so it needs the first package release) |
| [Case studies](../notebooks/case-studies/README.md) | Three timed analyses with figures, for papers and talks: cancer-gene structures, microbial functions, gut microbe–disease associations |
| [Protein structures](tutorials/protein-structures.md) | A structure listing, related-entry inspection and batch export |
| [Microbial functions](tutorials/microbial-functions.md) | An ecological annotation with its supporting rule trace |
| [Disease–microbe associations](tutorials/disease-associations.md) | Observations with provider identity, sample context and publications |

## Complete a task

1. [Install Braidworks](how-to/install.md): choose packages and create a local environment.
2. [Run a query](how-to/run-queries.md) from the command line, then
   [process a batch](how-to/process-a-batch.md).
   In a script or notebook, [work in Python](how-to/work-in-python.md).
3. [Read the results](how-to/check-results.md): check coverage, review matches, and export your data.

For interactive work, [use the browser](how-to/use-the-browser.md); to understand the
routes it shows, read [how routes are planned](explanation/how-routes-are-planned.md).

## Look up sources and interfaces

Use the [source catalogue](reference/sources.md), [key index](reference/keys-index.md),
[core contracts](reference/core-contracts.md) and [builder configuration](reference/weaver-configuration.md)
for exact capabilities, connections and construction rules. The [CLI reference](reference/cli/index.md)
lists every command and option; source READMEs link their specs and interpretation notes.
The [reference index](reference/index.md) brings these lookup paths together,
including [result shapes](reference/results.md) and [storage contracts](reference/persistence.md).

## More tasks for your data

| Task | Guide |
|---|---|
| Choose sources and prepare local data | [Choose and set up sources](how-to/choose-sources.md); the [source catalogue](reference/sources.md) lists each one |
| Find input and output field names | [Find a field](how-to/find-a-field.md): `braidworks find pdb structures`, `bw.find(...)` in Python, or the [key index](reference/keys-index.md) |
| Follow every related structure, pathway, or other entity | [Expansion and relationships](how-to/follow-related-entities.md) |
| Reuse lookups and continue saved work | [Cache and saved runs](how-to/cache-and-resume.md) |
| Prepare the optional local NCBI taxonomy database | [NCBI database setup](how-to/set-up-ncbi-database.md) |
| Limit requests to upstream services | [HTTP request pacing](how-to/set-request-rates.md) |
| Show Braidworks without a network connection | [Offline demo](how-to/run-the-offline-demo.md): `braidworks demo` |
| Inspect the source network offline | [Network view](network/braidworks-network.html), opened in a browser |

Exact command options are in the [CLI reference](reference/cli/index.md) (also
`braidworks --help` and each command's `--help`). Source-specific capabilities,
parameters, and interpretation notes live in the package READMEs linked from the
[source catalogue](reference/sources.md).

## Understand or extend Braidworks

For the overall model, start with [how Braidworks fits together](explanation/architecture.md).
For scientific interpretation, read [what a lookup result establishes](explanation/result-meaning.md);
for web APIs, local databases and sample data, [where the data comes from](explanation/where-data-comes-from.md).
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

What changed in each version: the [changelog](../CHANGELOG.md), with one per package
in each package folder, and the [GitHub releases](https://github.com/rafaelmdc/braidworks/releases).

For documentation contributors, the [Diátaxis map](internal/audits/documentation-diataxis.md)
records current page roles, gaps and proposed edits; [writing conventions](how-to/write-documentation.md)
explain how to preserve useful detail during a rewrite.

For older workflows, see [core 0.12 ambiguity changes](how-to/migrate-to-core-0.12.md) and
[core 0.13 batching and pacing changes](how-to/migrate-to-core-0.13.md).
[Current work](internal/NEXT.md) describes remaining project decisions.

[Roadmaps and original plans](internal/history.md), [audit records](internal/audits/README.md), and
[refactoring records](internal/refactoring/README.md) preserve design and validation history.
Their dates and completion notes matter; use the guides above for current behavior.
