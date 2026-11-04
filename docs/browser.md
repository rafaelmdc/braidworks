# Build and run a query in the browser

Use the optional browser interface to inspect a route, run inputs and export results.
First [install the server extra](installation.md#add-the-browser) with the sources you
need. Their API or local-data prerequisites still apply.

## Run a query

1. From the checkout, start `uv run --no-sync weaverkit serve`.
2. Open the localhost address printed by the server.
3. Choose the input type and target fields, inspect the route, then enter values and run.
4. Inspect coverage, review and error information before exporting JSON, CSV or TSV.

The route view shows execution progress and rerouting when a step fails. The offline
`weaverkit view` export only inspects the network; use `serve` for interactive execution.
See [result interpretation](explanation/result-meaning.md) and [exports](results.md).

## Process a batch

Enable **Batch inputs** and paste one identifier per line, or upload CSV/TSV with field
names as headers. Empty cells are absent inputs. Shared values, row overrides,
duplicate rows, query parameters and expansion budgets follow [CLI batch rules](usage.md#process-a-batch).
Inspect parent/source-row fields when expanding related entities.

Save a recipe or copy a generated command/script to reuse the query settings. Generated
CLI commands retain parameters and policies. Generated Python uses core's query service;
it does not require the browser server at execution time. See [artifact reference](reference/browser.md).

## Cache lookups and continue saved work

Expand **Cache and saved runs** to set a lookup-cache and/or run-store file. Blank paths
retain in-memory execution. Advanced controls set TTLs, payload budget and the run lease.
Paths refer to the server's disk; recipes and generated commands retain them, so inspect
paths before sharing a recipe.

Open **Saved runs** for the selected store, inspect a run and continue using its saved
settings. Review selectors start at **Leave pending**. Choose a candidate, accept an
observation or reject a row before continuing; duplicate inputs retain independent choices.
Cancellation retains the last completed checkpoint; an interrupted source read may repeat.
For storage identity, leases and retention, see [storage reference](reference/persistence.md).

For integrations using HTTP rather than the browser controls, use
[the endpoint reference](reference/browser.md).
