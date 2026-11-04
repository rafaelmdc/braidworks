"""Source identities and contradictory classifications remain visible."""

import httpx
import pytest
from gtdb_weaver import taxonomy
from gtdb_weaver.backends.api import GtdbApiBackend, _best_row
from gtdb_weaver.backends.local import GtdbLocalBackend


async def test_crosswalk_preserves_conflicts_and_never_selects_one_taxonomy(tmp_path):
    rows = [
        (1, "d__Bacteria;s__Species alpha", True, "GCF_B"),
        (1, "d__Bacteria;s__Species beta", True, "GCF_A"),
    ]
    errors = []
    for index, permuted in enumerate((rows, list(reversed(rows)), rows + rows)):
        path = tmp_path / f"{index}.sqlite"
        taxonomy.build_crosswalk_db(permuted, path, release="R1")
        with taxonomy.open_ro(path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM classification").fetchone()[0] == 2
        record = (
            await GtdbLocalBackend(db_path=path).fetch(
                "describe_taxonomy",
                [{"ncbi.taxon.id": 1}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
            )
        )[0]
        assert record.error and not record.found
        errors.append(record.error)
    assert errors[0] == errors[1] == errors[2]
    assert "Species alpha" in errors[0] and "Species beta" in errors[0]


def test_api_unrelated_hits_are_not_matches_and_representative_ties_are_stable():
    rows = [
        {
            "gtdbTaxonomy": "d__Bacteria;s__Species alpha",
            "isGtdbSpeciesRep": True,
            "accession": accession,
        }
        for accession in ("GCF_B", "GCF_A")
    ]
    assert _best_row(rows, "Unrelated species") is None
    assert _best_row(rows, "Species alpha")["accession"] == "GCF_A"
    assert _best_row(list(reversed(rows)), "Species alpha")["accession"] == "GCF_A"
    conflict = {**rows[0], "gtdbTaxonomy": "d__Archaea;s__Species alpha"}
    with pytest.raises(taxonomy.AmbiguousClassification):
        _best_row(rows + [conflict], "Species alpha")


async def test_api_conflicting_lineages_are_error_values():
    rows = [{"gtdbTaxonomy": f"d__{domain};s__Species alpha"} for domain in ["Bacteria", "Archaea"]]
    async with httpx.AsyncClient(
        base_url="https://source",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"rows": rows}),
        ),
    ) as client:
        records = await GtdbApiBackend(client=client).fetch(
            "describe_taxonomy",
            [{"organism.scientific_name": "Species alpha"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
    assert records[0].error and not records[0].found
