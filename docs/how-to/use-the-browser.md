# Build and run a query in the browser

Use the optional browser interface to inspect a route, run inputs and export results.
First [install the server extra](install.md#start-the-browser) with the sources you
need. Their API or local-data prerequisites still apply.

## Run a query

1. From the checkout, start `uv run braidworks serve`.
2. Open the localhost address printed by the server. If the port is taken (often an
   earlier server still running), `serve` says so and exits without printing an
   address: stop the other one (`make serve-stop`) or pass `--port 8766`.
3. Paste your IDs, one per line (commas also separate; names may contain spaces), or
   upload a list or table. To start from a ready-made query, click one of the examples
   under **Start from an example**.
4. Choose what they are (the most widely accepted input type is preselected).
5. Search for the fields you want in plain words and tick them. Fields no route can
   reach from your input are greyed out. Any options the route accepts, such as a
   species filter, appear below the fields.
6. Click **Get fields**. The table has one row per ID with its status, each value (lists
   show their size), and the fields still missing.

## Review, filter and download the results

- Click a status count (for example **need review**) to show only those rows; click it
  again to show all.
- A row paused for review lists its candidates. **Choose** one, **Accept** a flagged
  match, or **Reject** the row, then click **Resume**. Only the decided rows continue;
  undecided rows stay paused. Paused results are kept while the server runs (the most
  recent 32); after a restart, run the query again.
- **CSV**, **TSV** and **JSON** download exactly what `result.to_csv()` /
  `to_csv(sep="\t")` / `result.to_json()` give in Python for the same query.
- **How this was answered** shows the route that ran, step by step: each source and
  capability, what it took and gave, the backend used, how many rows it found, did not
  match, skipped (no input) or failed, and the options it ran with.
- **Sources to cite** lists every source the results drew on, with its licence and
  citation.

The network graph and the step-by-step builder are under **Explore sources**
(`/explore`): use them to see how sources connect, follow relationships, or set
review, cache and expansion settings. The offline `weaverkit view` export only
inspects the network. See [result interpretation](../explanation/result-meaning.md)
and [exports](check-results.md).

## Change advanced settings

**Advanced settings** under the form is collapsed by default. Open it to choose local
data or web APIs, take the best candidate instead of pausing for ambiguous matches, set a
minimum confidence, follow every member (or the first few) of lists in later steps, cap
the rows in one run, keep a lookup cache, or save a resumable run. A saved run's paused
rows resume from its store when you click **Resume**.

## Save and reuse examples

Click **Save as example**, name it, and it joins **Start from an example** in this
browser. Saved examples keep the IDs, fields, options and advanced settings, and are
shared with recipes saved in the **Explore sources** builder (recipes that pass through
relationships open there instead). Built-in examples appear only when the installed
sources can answer them. Delete your own with ×.

## Process a batch

Paste one identifier per line, or upload a CSV/TSV whose headers name each column's
field (rows may then start from different fields, and step 2 is skipped). Empty cells are absent inputs. Shared values, row overrides,
duplicate rows, query parameters and expansion budgets follow [CLI batch rules](process-a-batch.md).
Inspect parent/source-row fields when expanding related entities.

Save a recipe or copy a generated command/script to reuse the query settings. Generated
CLI commands retain parameters and policies. Generated Python uses core's query service;
it does not require the browser server at execution time. See [artifact reference](../reference/browser.md).

## Cache lookups and continue saved work

On the landing page, set **Lookup cache file** or **Save a resumable run in** under
**Advanced settings**. In the **Explore sources** builder, expand **Cache and saved runs**
to set a lookup-cache and/or run-store file. Blank paths
retain in-memory execution. Advanced controls set TTLs, payload budget and the run lease.
Paths are on the server's disk and must stay inside its data directory: the folder
`braidworks serve` was started in, or the one given with `--data-dir`. Relative paths
such as `data/runs.sqlite` resolve inside it; paths outside it are refused. Recipes and
generated commands retain the paths, so inspect them before sharing a recipe.

Open **Saved runs** for the selected store, inspect a run and continue using its saved
settings. Review selectors start at **Leave pending**. Choose a candidate, accept an
observation or reject a row before continuing; duplicate inputs retain independent choices.
Cancellation retains the last completed checkpoint; an interrupted source read may repeat.
For storage identity, leases and retention, see [storage reference](../reference/persistence.md).

For integrations using HTTP rather than the browser controls, use
[the endpoint reference](../reference/browser.md).
