# Inspect the evidence behind a disease–microbe association

In this lesson, you will inspect a disease record in Disbiome, retrieve its reported
microbial associations from faecal samples, and follow an observation to its publication.
You will save the result with coverage and references for later inspection.

## Install the source

From your Braidworks checkout, run:

```bash
uv sync --package disbiome-weaver
```

Use Python 3.12+ and uv, as in [installation](../installation.md). This selection
updates the local `.venv` and can remove previously selected packages. Disbiome requires
a separately acquired local database; the next script downloads its real source tables
on first use, then reuses the database. Network access is needed for that first build.
The SQLite database occupied about 45 MB in our verification; provider size can change.

## Retrieve a disease record and its observations

Save this complete script as `inspect_disease.py` in the checkout:

```python
import asyncio
import json
from pathlib import Path

from braidworks import async_fetch
from braidworks.core import BraidRegistry
from disbiome_weaver import build_disbiome_weaver_configured


async def main():
    async with build_disbiome_weaver_configured(
        db_path="data/tutorial-disbiome.sqlite", auto_setup=True,
    ) as weaver:
        registry = BraidRegistry()
        registry.register(weaver)
        disease = await async_fetch(
            "disease.disbiome.record", ids=["1"],
            have="disease.disbiome.id", registry=registry,
        )
        print("Disease:", disease.get("1").get("disease.disbiome.record"))
        associations = await async_fetch(
            "microbe.disease.taxa", ids=["1"],
            have="disease.disbiome.id", registry=registry,
            params={"sample": "Faeces"},
        )
        print("Unresolved:", associations.unresolved)
        print("Reviews:", associations.review_required, associations.review_queue)
        print("Errors:", associations.errors)
        observations = associations.get("1").get("microbe.disease.taxa")
        if observations is not None:
            print("Experiments:", observations["experiment_count"])
            print("Distinct taxa:", observations["observed_taxon_count"])
            for record in observations["records"][:3]:
                publication = record.get("publication") or {}
                print(record["taxid"], record["direction"], record["method"])
                print(publication.get("title"), publication.get("pubmed_url"))
        Path("disease-associations.json").write_text(
            json.dumps(associations.to_json(), indent=2), encoding="utf-8",
        )


asyncio.run(main())
```

`auto_setup=True` authorizes acquisition into the named local path. The database is
ignored by git; keep it on local disk. Run the script:

```bash
uv run --no-sync python inspect_disease.py
```

First, check the printed disease identity: provider disease ID `1` described `Autism`
in the verified data. This is a Disbiome identifier, not a MedDRA code; the source
record includes the separate MedDRA identity. Inspect that record before interpreting
its associations.

Next, look for experiment and distinct-taxon counts and the first three observations
with method, direction and publication title. The verified filtered lookup returned
observations including taxid `1591` and a publication titled *Gastrointestinal microbiota
in children with autism in Slovakia.* Counts can change with the acquired source tables.

Check that unresolved, review and error lists are empty for this example. If a requested
value is absent, the script still saves its outcome; inspect that before using the data.
`Faeces` is an exact provider sample filter, not an inferred anatomical classification.

## Inspect the retained evidence

Open `disease-associations.json`. Under `resolved`, inspect the `microbe.disease.taxa`
value: it retains experiment records, publication evidence, matched disease IDs,
coverage scope and effective filters. The script prints only three records; the file
retains the returned result. `references`, `unresolved`, `review_required`,
`review_queue` and `errors` sit alongside the values.

Notice that experiment count and distinct-taxon count answer different questions.
An elevated or reduced observation is a reported association under its study's
conditions. It does not establish causation, a diagnostic marker, or a treatment
recommendation. Follow the publication and consider study methods and controls.

You now have an evidence trail from provider disease identity to observed associations
and publications. Repeating the script reuses the local database and overwrites the
JSON file; rename the export before repeating if you need to retain it. The four source
tables are acquired independently, so the build does not represent a frozen upstream
snapshot. This `FetchResult` export is not a CLI run archive or resume checkpoint.

For other identifiers and filters, use the
[Disbiome reference](../../weavers/disbiome_weaver/README.md). For interpretation of
lookup failures and partial results, use [result interpretation](../results.md).
