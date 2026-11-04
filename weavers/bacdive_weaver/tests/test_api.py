"""Unit tests for the BacDive api backend — the novel type-strain logic.

Driven by ``httpx.MockTransport`` so they are offline and deterministic. They
exercise: type-strain selection (short-circuit), dict-vs-list subfield
normalization, misses, the scan cap, and per-entity error handling.
"""

from __future__ import annotations

import json

import httpx
from bacdive_weaver.backends.api import BacdiveApiBackend

CAP = "describe_traits"
ALL_OUTPUTS = frozenset(
    {
        "microbe.trait.gram_stain",
        "microbe.trait.cell_shape",
        "microbe.trait.motility",
        "microbe.trait.spore_formation",
        "microbe.trait.oxygen_tolerance",
        "microbe.trait.optimum_temp",
        "microbe.trait.optimum_ph",
    }
)


def _backend(taxon, records, *, max_strains_scanned=1000, taxon_status=200, calls=None):
    """Build a backend over canned data.

    ``taxon``: {"/taxon/Genus/species": {"results": [...], "next": ...}}.
    ``records``: {strain_id: record_dict}. ``/fetch/{a;b;c}`` is served by splitting
    the semicolon ids and returning those records (the real batch shape).
    ``calls``: optional list to append each requested path to (assert batching).
    """

    # Successful source fixtures include the taxonomy echoed by real strain records.
    from copy import deepcopy

    records = deepcopy(records)
    for suffix, payload in taxon.items():
        parts = suffix.split("?", 1)[0].split("/")
        species_name = " ".join(parts[-2:])
        for identifier in payload["results"]:
            if identifier in records:
                section = records[identifier]["Name and taxonomic classification"]
                for row in section if isinstance(section, list) else [section]:
                    row.setdefault("species", species_name)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if calls is not None:
            calls.append(path)
        if "/taxon/" in path:
            full = str(request.url)  # includes the query, so ?page=N routes are distinct
            for suffix, payload in taxon.items():
                if full.endswith(suffix):
                    return httpx.Response(200, content=json.dumps(payload))
            if taxon_status != 200:
                return httpx.Response(taxon_status, content=b"{}")
            return httpx.Response(200, content=json.dumps({"results": [], "next": None}))
        if "/fetch/" in path:
            ids = [int(i) for i in path.rsplit("/", 1)[1].split(";") if i]
            results = {str(i): records[i] for i in ids if i in records}
            return httpx.Response(200, content=json.dumps({"results": results}))
        return httpx.Response(404, content=b"{}")

    client = httpx.AsyncClient(base_url="https://t/v2", transport=httpx.MockTransport(handler))
    return BacdiveApiBackend(client=client, max_strains_scanned=max_strains_scanned)


def _typed(flag):
    return {"Name and taxonomic classification": {"type strain": flag}}


async def _one(backend, name):
    records = await backend.fetch(
        CAP,
        [{"organism.scientific_name": name}],
        requested_outputs=ALL_OUTPUTS,
        groups_to_compute=frozenset(),
    )
    assert len(records) == 1
    return records[0]


async def test_selects_type_strain_short_circuiting_non_type():
    taxon = {"/taxon/Escherichia/coli": {"results": [1, 2], "next": None}}
    records = {
        1: _typed("no"),
        2: {
            "Name and taxonomic classification": {"type strain": "yes"},
            "Morphology": {
                "cell morphology": {"gram stain": "positive", "cell shape": "coccus-shaped"}
            },
        },
    }
    record = await _one(_backend(taxon, records), "Escherichia coli")
    assert record.found is True
    assert record.values["microbe.trait.gram_stain"] == "positive"
    assert record.values["microbe.trait.cell_shape"] == "coccus-shaped"


async def test_normalizes_list_and_dict_subfields():
    # cell morphology arrives as a LIST; culture temp as a LIST with an optimum entry.
    record = {
        "Name and taxonomic classification": [{"type strain": "yes"}],
        "Morphology": {"cell morphology": [{"gram stain": "negative", "motility": "yes"}]},
        "Physiology and metabolism": {"oxygen tolerance": [{"oxygen tolerance": "anaerobe"}]},
        "Culture and growth conditions": {
            "culture temp": [
                {"type": "range", "temperature": "20-45"},
                {"type": "optimum", "temperature": "37"},
            ],
            "culture pH": {"type": "optimum", "pH": "7.0"},
        },
    }
    taxon = {"/taxon/Bacillus/subtilis": {"results": [9], "next": None}}
    values = (await _one(_backend(taxon, {9: record}), "Bacillus subtilis")).values
    assert values["microbe.trait.motility"] == "yes"
    assert values["microbe.trait.oxygen_tolerance"] == "anaerobe"
    assert values["microbe.trait.optimum_temp"] == "37"  # the optimum entry, not the range
    assert values["microbe.trait.optimum_ph"] == "7.0"  # from a dict (single) subfield


async def test_no_type_strain_in_results_is_a_miss():
    taxon = {"/taxon/Genus/species": {"results": [1], "next": None}}
    record = await _one(_backend(taxon, {1: _typed("no")}), "Genus species")
    assert record.found is False and record.error is None


async def test_empty_taxon_is_a_miss():
    record = await _one(_backend({}, {}), "No such")
    assert record.found is False


async def test_batch_fetches_ids_in_one_call():
    # 3 ids should be fetched in a single semicolon-joined /fetch call, not 3 calls.
    taxon = {"/taxon/Many/strains": {"results": [1, 2, 3], "next": None}}
    records = {1: _typed("no"), 2: _typed("no"), 3: _typed("yes")}
    calls: list[str] = []
    record = await _one(_backend(taxon, records, calls=calls), "Many strains")
    assert record.found is True
    fetch_calls = [c for c in calls if "/fetch/" in c]
    assert len(fetch_calls) == 1 and fetch_calls[0].endswith("/fetch/1;2;3")  # one batched call


async def test_scan_cap_stops_searching():
    # cap below the type strain's position -> not found (and bounds the work).
    taxon = {"/taxon/Many/strains": {"results": [1, 2, 3], "next": None}}
    records = {1: _typed("no"), 2: _typed("no"), 3: _typed("yes")}
    record = await _one(_backend(taxon, records, max_strains_scanned=2), "Many strains")
    assert not record.found and record.error
    assert "complete=false" in record.error  # incomplete is not a biological miss


async def test_paginates_via_next():
    taxon = {
        "/taxon/Two/pages": {"results": [1], "next": "https://t/v2/taxon/Two/pages?page=2"},
        "/taxon/Two/pages?page=2": {"results": [2], "next": None},
    }
    # _backend matches on path suffix; the second page's path is the same, so route
    # both via a single entry that returns page 1 then chains — simplest: type strain on page 2.
    records = {1: _typed("no"), 2: _typed("yes")}
    record = await _one(_backend(taxon, records), "Two pages")
    assert record.found is True


async def test_http_error_becomes_per_entity_error():
    record = await _one(_backend({}, {}, taxon_status=500), "Boom now")
    assert record.found is False and record.error is not None and "BacDive" in record.error


async def test_blank_name_is_a_miss_without_calling_api():
    # No genus -> no request issued; a clean miss.
    record = await _one(_backend({}, {}), "   ")
    assert record.found is False and record.error is None


def test_fingerprint_is_stable_and_real():
    fp = BacdiveApiBackend().fingerprint()
    assert fp and fp.lower() not in ("", "unknown") and "TODO" not in fp


async def test_scan_fetch_does_not_exceed_remaining_budget():
    calls = []
    backend = _backend(
        {"/taxon/Many/strains": {"results": [1, 2, 3], "next": None}},
        {1: _typed("no"), 2: _typed("no"), 3: _typed("yes")},
        max_strains_scanned=2,
        calls=calls,
    )
    assert (await _one(backend, "Many strains")).error
    assert [call for call in calls if "/fetch/" in call] == ["/v2/fetch/1;2"]


async def test_exhausted_catalog_at_exact_budget_is_definitive_miss():
    backend = _backend(
        {"/taxon/Many/strains": {"results": [1, 2], "next": None}},
        {1: _typed("no"), 2: _typed("no")},
        max_strains_scanned=2,
    )
    result = await _one(backend, "Many strains")
    assert not result.found and result.error is None


def test_scan_budget_changes_source_fingerprint():
    assert BacdiveApiBackend(max_strains_scanned=2).fingerprint() != (
        BacdiveApiBackend(max_strains_scanned=3).fingerprint()
    )


def test_builders_share_default_budget_and_honor_explicit_budget():
    from bacdive_weaver.factory import build_bacdive_weaver, build_bacdive_weaver_configured

    default = build_bacdive_weaver().backend_fingerprint("api")
    assert default == build_bacdive_weaver_configured().backend_fingerprint("api")
    assert default != build_bacdive_weaver(max_strains_scanned=2).backend_fingerprint("api")


async def test_genus_and_qualified_names_are_rejected_without_lookup():
    calls = []
    backend = _backend({}, {}, calls=calls)
    for name in [
        "Escherichia",
        "Escherichia coli subsp. coli",
        "Escherichia sp.",
        "Escherichia coli strain K12",
    ]:
        record = await _one(backend, name)
        assert record.error and not record.found
    assert calls == []


async def test_type_identity_is_stable_across_listing_order_and_pages():
    records = {1: _typed("yes"), 2: _typed("yes")}
    outputs = []
    for taxon in [
        {"/taxon/Escherichia/coli": {"results": [2, 1, 2], "next": None}},
        {
            "/taxon/Escherichia/coli": {
                "results": [2],
                "next": "https://t/v2/taxon/Escherichia/coli?page=2",
            },
            "/taxon/Escherichia/coli?page=2": {"results": [1], "next": None},
        },
    ]:
        record = await _one(_backend(taxon, records), "Escherichia coli")
        assert record.found
        outputs.append(record.values["microbe.trait.records"])
    assert outputs[0] == outputs[1]
    assert outputs[0]["strain_id"] == 1
    assert outputs[0]["scope"] == "type_strain_representative"


async def test_conflicting_traits_omit_scalar_and_preserve_units_references():
    taxon = {"/taxon/Escherichia/coli": {"results": [1], "next": None}}
    measurements = [
        {"type": "optimum", "temperature": value, "unit": "C", "reference": reference}
        for value, reference in [(37, "publication-a"), (30, "publication-b")]
    ]
    values = []
    for observed in (measurements, list(reversed(measurements))):
        source = {**_typed("yes"), "Culture and growth conditions": {"culture temp": observed}}
        record = await _one(_backend(taxon, {1: source}), "Escherichia coli")
        assert record.found and record.warnings
        assert "microbe.trait.optimum_temp" not in record.values
        values.append(record.values)
    assert values[0] == values[1]
    evidence = values[0]["microbe.trait.records"]
    assert evidence["conflicts"]["microbe.trait.optimum_temp"] == ["30", "37"]
    assert {
        row["reference"]
        for row in evidence["source"]["Culture and growth conditions"]["culture temp"]
    } == {"publication-a", "publication-b"}


async def test_mismatched_source_species_is_an_error():
    taxon = {"/taxon/Escherichia/coli": {"results": [1], "next": None}}
    source = {
        "Name and taxonomic classification": {"type strain": "yes", "species": "Bacillus subtilis"}
    }
    record = await _one(_backend(taxon, {1: source}), "Escherichia coli")
    assert record.error and not record.found
