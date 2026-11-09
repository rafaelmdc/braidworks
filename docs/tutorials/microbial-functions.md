# Trace a microbial functional annotation to its evidence

In this lesson, you will retrieve putative ecological functions for *Methylococcus*,
then inspect the FAPROTAX rules supporting them. You will finish with a JSON result
that retains the annotation, its evidence and the lookup outcome.

## Prepare the two sources

From your Braidworks checkout, install every source, including NCBI and FAPROTAX:

```bash
uv sync --all-extras
```

Use Python 3.12+ and uv, as in [installation](../how-to/install.md).
The lesson uses live NCBI taxonomy and bundled FAPROTAX rules; it does not acquire a
local taxonomy database. Network access to NCBI is required.

## Retrieve one annotation

Run this from the checkout:

```bash
uv run braidworks get Methylococcus --have organism.name \
    --want microbe.ecology.functional_groups --only ncbi,faprotax --policy api_first
```

Look for a resolved row containing `methanotrophy` and `methylotrophy` among its
functional groups. The verified example also returned `chemoheterotrophy` and
`hydrocarbon_degradation`. Source updates may change observations; inspect diagnostics
if your row is `[unresolved]` or `[review]`.

Notice that the query starts with an organism name. NCBI supplies its lineage, and
FAPROTAX matches that lineage locally. These annotations are taxonomic affiliations,
not measurements of a particular strain's metabolism.

## Save the annotation with its evidence

Repeat the lookup, adding the evidence field and JSON output:

```bash
uv run braidworks get Methylococcus --have organism.name \
    --want microbe.ecology.functional_groups,microbe.ecology.evidence \
    --only ncbi,faprotax --policy api_first --format json > methylococcus.json
```

The shell overwrites an existing `methylococcus.json`; use a new filename to retain
an earlier result. Save the script below as `inspect_ecology.py`:

```python
import json
from pathlib import Path

data = json.loads(Path("methylococcus.json").read_text())
row = data["rows"][0]
print("Outcome:", row["status"], "Missing:", row["missing"])
print("Review:", row["status"] == "review", "Errors:", data["result"]["errors"])
evidence = row.get("microbe.ecology.evidence")
if evidence is not None:
    print("Source:", evidence["source"])
    print("Meaning:", evidence["interpretation"])
    for operation in evidence["groups"]["methanotrophy"]["operations"]:
        if operation["operation"] == "member" and operation["operand"]:
            print(operation["value"], operation.get("reference"))
```

Run it:

```bash
uv run python inspect_ecology.py
```

Check that `Missing` is empty, `Review` is false and `Errors` is empty before using
the annotation. The verified evidence identifies `faprotax-1.2.12` and includes
matched patterns for `Methylococcaceae` and `Methylococcus`, with source references.
The trace lets you see which rule supported the affiliation.

You have now followed an annotation back to its source rule instead of retaining
only a function label. Keep the JSON with your analysis. A rule's literature supports
the clade affiliation; it does not demonstrate the function in every queried isolate.
An empty annotation would likewise not prove functional absence.

For your own organism table, continue with [batch usage](../how-to/process-a-batch.md).
The [FAPROTAX reference](../../weavers/faprotax_weaver/README.md) describes membership
rules and evidence scope; [result interpretation](../how-to/check-results.md) covers partial and
uncertain observations.
