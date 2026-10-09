"""Known-row, missing-row and projection checks beyond the shared order contract."""

from braidworks.core import Strand, StrandSet, WeaveStatus
from example_weaver.backends.local import ExampleLocalBackend
from example_weaver.factory import build_example_weaver

GRAM = "microbe.trait.gram_stain"
TEMP = "microbe.trait.optimum_temp"


async def test_real_rows_miss_duplicates_and_requested_only_outputs():
    taxids = ["562", "1423", "1280", "1773", "1351", "999999999", "562"]
    inputs = [
        StrandSet.from_strands(f"row-{i}", [Strand("ncbi.taxon.id", taxid)])
        for i, taxid in enumerate(taxids)
    ]
    async with build_example_weaver() as weaver:
        gram = await weaver.execute_batch(
            "describe_traits", inputs, requested_outputs=frozenset({GRAM}), backend="local"
        )
        growth = await weaver.execute_batch(
            "describe_traits", inputs, requested_outputs=frozenset({TEMP}), backend="local"
        )
    assert len(gram) == len(growth) == len(inputs)
    expected_grams = ["negative", "positive", "positive", "positive", "positive", None, "negative"]
    expected_temps = ["37", "30", "37", "37", "37", None, "37"]
    for results, output, expected in [(gram, GRAM, expected_grams), (growth, TEMP, expected_temps)]:
        for result, value in zip(results, expected, strict=True):
            if value is None:
                assert result.status is WeaveStatus.NO_MATCH
                assert result.strands == ()
            else:
                assert result.status is WeaveStatus.OK
                assert [(strand.type_id, strand.value) for strand in result.strands] == [
                    (output, value)
                ]


async def test_backend_results_do_not_mutate_bundled_table():
    backend = ExampleLocalBackend()
    query = {"ncbi.taxon.id": "562"}
    records = await backend.fetch(
        "describe_traits",
        [query, query],
        requested_outputs=frozenset({GRAM}),
        groups_to_compute=frozenset({"traits.core"}),
    )
    records[0].values[GRAM] = "changed"
    assert records[1].values[GRAM] == "negative"
    again = await backend.fetch(
        "describe_traits",
        [query],
        requested_outputs=frozenset({GRAM}),
        groups_to_compute=frozenset({"traits.core"}),
    )
    assert again[0].values[GRAM] == "negative"
