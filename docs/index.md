# Braidworks documentation

Braidworks connects lookups across biological data sources. Start with a small query,
choose the sources your analysis needs, then scale to a batch. The
[README](../README.md) introduces the tool and includes a first command.

## Get started

1. [Install Braidworks](installation.md): choose packages and create a local environment.
2. [Run a query](usage.md): use the CLI, Python, or browser, then process a batch.
3. [Read the results](results.md): check coverage, review matches, and export your data.

## Work with your data

| Task | Guide |
|---|---|
| Choose sources and prepare local data | [Source catalogue](sources.md) |
| Find input and output field names | [Key index](keys-index.md), generated from the weavers |
| Follow every related structure, pathway, or other entity | [Expansion and relationships](usage.md#follow-related-entities) |
| Reuse lookups and continue saved work | [Cache and saved runs](persistence.md) |
| Prepare the optional local NCBI taxonomy database | [NCBI database setup](database.md) |
| Limit requests to upstream services | [HTTP request pacing](request-pacing.md) |
| Inspect the source network offline | [Network view](braidworks-network.html), opened in a browser |

Exact command options are available through `braidworks --help`,
`braidworks weave --help`, and each subcommand's `--help`. Source-specific capabilities,
parameters, and interpretation notes live in the package READMEs linked from the
[source catalogue](sources.md).

## Understand or extend Braidworks

| Task | Documentation |
|---|---|
| Understand planning, execution, and package boundaries | [Architecture](architecture.md) |
| Check framework contracts while implementing an adapter | [Core contracts](core-contracts.md) |
| Configure builders and manage their resources | [Weaver configuration](weaver-configuration.md) |
| Find code in the workspace | [Repository structure](repo-structure.md) |
| Contribute a fix or new source | [Contributing](../CONTRIBUTING.md), [repository rules](../AGENTS.md), and [weaverkit](../weaverkit/README.md) |
| Implement a weaver's backend | [Implementation guide](weaver-implementation-guide.md) |
| Build and check release artifacts | [Release rehearsal](releasing.md) |
| Use the experimental distributed adapter | [braidworks-arq](../braidworks-arq/README.md) |

## Upgrade notes and project history

For older workflows, see [core 0.12 ambiguity changes](migrating-to-0.12.md) and
[core 0.13 batching and pacing changes](migrating-to-0.13.md).
[Current work](NEXT.md) describes remaining project decisions.

[Roadmaps and original plans](history.md), [audit records](audits/README.md), and
[refactoring records](refactoring/README.md) preserve design and validation history.
Their dates and completion notes matter; use the guides above for current behavior.
