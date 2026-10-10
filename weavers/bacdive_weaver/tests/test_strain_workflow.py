"""List all observed strain identities, then describe exact records in bulk."""

import httpx
from bacdive_weaver.backends.api import BacdiveApiBackend
from bacdive_weaver.fixture import _handler


async def test_list_to_exact_strain_batch_and_unknown_id():
    calls = []

    def handler(request):
        calls.append(request)
        return _handler(request)

    async with httpx.AsyncClient(
        base_url="https://fixture/v2", transport=httpx.MockTransport(handler)
    ) as client:
        backend = BacdiveApiBackend(client=client)
        listing = (
            await backend.fetch(
                "list_strains",
                [{"organism.scientific_name": "Escherichia coli"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset({"strains"}),
            )
        )[0]
        assert listing.values["microbe.bacdive.strain_id"] == [1, 2]
        assert len(calls) == 1  # listing never fetches trait records
        results = await backend.fetch(
            "describe_strain",
            [{"microbe.bacdive.strain_id": i} for i in [1, 2, 999, 2]],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"identity", "evidence"}),
        )
        assert len(calls) == 2
        assert not results[2].found and results[2].error is None
        assert results[0].values["microbe.bacdive.strain"]["type_strain"] == "no"
        assert results[1].values["microbe.bacdive.strain"]["type_strain"] == "yes"
        assert results[1].values["microbe.trait.records"]["scope"] == "exact_strain"
        results[1].values["microbe.bacdive.strain"]["taxonomy"][0]["species"] = "mutated"
        assert (
            results[3].values["microbe.bacdive.strain"]["taxonomy"][0]["species"]
            == "Escherichia coli"
        )


async def test_exact_strain_fetch_chunks_at_provider_hundred_id_limit():
    from bacdive_weaver.fixture import _TYPE_STRAIN

    calls = []

    def handler(request):
        ids = request.url.path.rsplit("/", 1)[1].split(";")
        calls.append(ids)
        return httpx.Response(
            200, json={"results": {identifier: _TYPE_STRAIN for identifier in ids}}
        )

    async with httpx.AsyncClient(
        base_url="https://fixture/v2", transport=httpx.MockTransport(handler)
    ) as client:
        records = await BacdiveApiBackend(client=client).fetch(
            "describe_strain",
            [{"microbe.bacdive.strain_id": i} for i in range(1, 102)],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"identity"}),
        )
        assert [len(chunk) for chunk in calls] == [100, 1]
        assert len(records) == 101 and all(record.found for record in records)


async def test_exact_traits_warn_on_conflicts_and_malformed_flag_is_error():
    from copy import deepcopy

    from bacdive_weaver.fixture import _TYPE_STRAIN

    source = deepcopy(_TYPE_STRAIN)
    source["Morphology"]["cell morphology"] = [
        {"gram stain": "positive"},
        {"gram stain": "negative"},
    ]

    def handler(request):
        return httpx.Response(200, json={"results": {"2": source}})

    async with httpx.AsyncClient(
        base_url="https://fixture/v2", transport=httpx.MockTransport(handler)
    ) as client:
        backend = BacdiveApiBackend(client=client)

        async def fetch():
            return (
                await backend.fetch(
                    "describe_strain",
                    [{"microbe.bacdive.strain_id": 2}],
                    requested_outputs=frozenset(),
                    groups_to_compute=frozenset({"morphology"}),
                )
            )[0]

        record = await fetch()
        assert record.found and record.warnings
        assert "microbe.trait.gram_stain" not in record.values
        source["Name and taxonomic classification"]["type strain"] = ["yes"]
        malformed = await fetch()
        assert malformed.error and not malformed.found
