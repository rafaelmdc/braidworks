"""Source schema rules for the private teaching CSV parser."""

import pytest
from example_weaver.backends import local

HEADER = "tax_id,gram_stain,optimum_temp\n"


def test_valid_rows_column_order_and_empty_traits():
    assert local._parse_table("optimum_temp,tax_id,gram_stain\n37,562,negative\n,1423,\n") == {
        "562": {"microbe.trait.gram_stain": "negative", "microbe.trait.optimum_temp": "37"},
        "1423": {},
    }
    assert local._parse_table(HEADER) == {}


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "tax_id,gram_stain\n562,negative\n",
        "tax_id,gram_stain,gram_stain\n",
        HEADER + "562,negative\n",
        HEADER + "562,negative,37,extra\n",
        HEADER + ",negative,37\n",
        HEADER + "0,negative,37\n",
        HEADER + "-1,negative,37\n",
        HEADER + "taxon,negative,37\n",
        HEADER + "562,negative,37\n562,positive,30\n",
        HEADER + "562,negative,37\n0562,positive,30\n",
        HEADER + '562,"unfinished,37\n',
    ],
)
def test_malformed_schema_or_duplicate_identity_is_rejected(raw):
    with pytest.raises(local._InvalidTable):
        local._parse_table(raw)


async def test_invalid_source_yields_errors_for_every_input(monkeypatch):
    def invalid():
        return local._parse_table(HEADER + "562,negative\n")

    monkeypatch.setattr(local, "_load_table", invalid)
    queries = [{"ncbi.taxon.id": "562"}, {"ncbi.taxon.id": "missing"}]
    records = await local.ExampleLocalBackend().fetch(
        "describe_traits", queries, requested_outputs=frozenset(), groups_to_compute=frozenset()
    )
    assert [record.query for record in records] == queries
    assert all(record.error and not record.found for record in records)
