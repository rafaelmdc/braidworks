import asyncio

import httpx
from bacdive_weaver.backends.api import BacdiveApiBackend


async def main():
    for status, body in [(404, b"{}"), (200, b"bad")]:
        async with httpx.AsyncClient(
            base_url="https://fixture/v2",
            transport=httpx.MockTransport(
                lambda request, status=status, body=body: httpx.Response(status, content=body)
            ),
        ) as client:
            backend = BacdiveApiBackend(client=client)
            try:
                records = await backend.fetch(
                    "describe_traits",
                    [{"organism.scientific_name": "No such"}],
                    requested_outputs=frozenset(),
                    groups_to_compute=frozenset(),
                )
                print(status, records[0].found, records[0].error)
            except Exception as error:  # noqa: BLE001 - reports escaped exception types
                print(status, "escaped", type(error).__name__)
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if "/taxon/" in request.url.path:
            return httpx.Response(200, json={"results": [2, 1], "next": None})
        return httpx.Response(
            200,
            json={
                "results": {
                    "1": {
                        "Name and taxonomic classification": {"type strain": "yes"},
                        "Morphology": {"cell morphology": {"gram stain": "negative"}},
                    },
                    "2": {
                        "Name and taxonomic classification": {"type strain": "yes"},
                        "Morphology": {"cell morphology": {"gram stain": "positive"}},
                    },
                }
            },
        )

    async with httpx.AsyncClient(
        base_url="https://fixture/v2", transport=httpx.MockTransport(handler)
    ) as client:
        backend = BacdiveApiBackend(client=client)
        out = await backend.fetch(
            "describe_traits",
            [{"organism.scientific_name": "Genus"}, {"organism.scientific_name": "Genus"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
        )
        print("Genus duplicate", out[0].values, "requests", len(calls))
    print(
        "Budget fingerprint equal",
        BacdiveApiBackend(max_strains_scanned=1).fingerprint()
        == BacdiveApiBackend(max_strains_scanned=1000).fingerprint(),
    )


asyncio.run(main())
