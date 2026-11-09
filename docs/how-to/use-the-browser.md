# Use the browser

Task recipes for the browser interface. New to it? Work through
[your first query in the browser](../tutorials/first-query-in-the-browser.md) first.
You need the [browser extra installed](install.md#start-the-browser) with the sources
you use; their API or local-data prerequisites still apply.

## Start the browser

From the checkout, run `uv run braidworks serve` and open the address it prints.

If the port is taken (often an earlier server still running), `serve` says so and
exits without printing an address. Stop the other one with `make serve-stop`, or pass
another port: `uv run braidworks serve --port 8766`.

## Run a query

1. Paste your IDs into **Your IDs**, one per line. Commas and semicolons also separate
   IDs; spaces do not, so names such as `Escherichia coli` stay one ID.
2. Under **What are they?**, choose the input type. The most widely accepted one is
   preselected; **Another input type** lists the rest.
3. Under **What do you want?**, search for fields in plain words and tick them. Fields
   no route reaches from your input are greyed out with "no route from …".
4. Fill in any **Options for this route**, such as UniProt's `organism` for gene
   symbols.
5. Click **Get fields**.

Each row of the table is one ID, labelled by what you pasted, with its status, each
value (lists show their size, such as "321 in total" or "25 of 312"), and the fields
still **Missing**. Read [what a lookup result establishes](../explanation/result-meaning.md)
before drawing conclusions from an `unresolved` row.

## Process a batch from a file

Click **Upload a list or table…**:

- A `.txt` file with one ID per line fills **Your IDs**.
- A `.csv` or `.tsv` file whose header row names each column's field is used as a table:
  rows can start from different fields, empty cells are absent inputs, and **What are
  they?** is skipped. Click **Use pasted IDs instead** to go back.

Duplicate rows stay separate rows. Batches follow the same rules as the
[command line](process-a-batch.md).

## Review paused matches

A row whose match was ambiguous (or that a source flagged for a check) is shown as
`review`, with its candidates and their confidence.

1. For each paused row, click **Choose** on a candidate, **Accept** a flagged match, or
   **Reject** the row.
2. Click **Resume**. Only the rows you decided continue; undecided rows stay paused, so
   you can decide them later.

The server keeps paused results while it runs (the most recent 32). After a restart,
run the query again, or save a resumable run (below) to keep paused rows on disk.

## Filter, download and cite the results

- Click a status count, such as **1 unresolved**, to show only those rows; click it
  again to show all.
- Click **CSV**, **TSV** or **JSON** to download the table. The files are exactly what
  `result.to_csv()`, `result.to_csv(sep="\t")` and `result.to_json()` give in Python, and
  what `braidworks get --format csv|tsv|json` prints, for the same query.
- **Sources to cite** lists each source the results drew on, with its licence and
  citation.
- **How this was answered** shows the route that ran, step by step, with how many rows
  each step found, did not match, skipped or failed. [How routes are planned](../explanation/how-routes-are-planned.md)
  explains it.

## Change advanced settings

Open **Advanced settings** (collapsed by default) to:

| To | Set |
|---|---|
| Use only local databases, or only web APIs | **Local data or web APIs** |
| Take the best candidate instead of pausing | **Ambiguous matches** → Take the best candidate (the row stays flagged) |
| Pause low-scoring matches for review | **Minimum confidence** |
| Get a row for every member of a list a later step needs | **When a step returns a list** → Follow every member (or the first few, with **How many to follow**) |
| Cap a large expansion | **Most rows in one run** |

## Cache lookups and keep resumable runs

Under **Advanced settings**, set **Lookup cache file** (for example
`data/lookups.sqlite`) to reuse earlier answers, and **Save a resumable run in** (for
example `data/runs.sqlite`, optionally with a **Run name**) to keep the run on disk. A
saved run's paused rows resume from that file when you click **Resume**.

Paths are on the server's disk and must stay inside its data directory: the folder
`braidworks serve` was started in, or the one given with `--data-dir`. Paths outside it
are refused. To list saved runs and continue one with its original settings, use
**Saved runs** in **Explore sources** or the [command line](cache-and-resume.md). For
cache lifetimes, leases and retention, see the [storage reference](../reference/persistence.md).

## Save and reuse examples

1. Set up a query, then click **Save as example** and type a name.
2. It appears under **Start from an example** in this browser, with its IDs, fields,
   options and advanced settings. Click it to load it; × deletes it.

Built-in examples appear only when the installed sources can answer them. Recipes saved
in the **Explore sources** builder appear here too, except those that pass through
relationships, which open in Explore.

## Explore the sources and follow relationships

Click **Explore sources** (`/explore`) to see the network of installed sources, preview
a route on the graph, or build a query that passes through a relationship (for example
every ortholog of a gene). The builder there can also copy the equivalent command line
and Python script; see the [endpoint reference](../reference/browser.md) for what they
contain. **← Look up** returns to the form.

For integrations that call the server over HTTP, use [the endpoint reference](../reference/browser.md).
