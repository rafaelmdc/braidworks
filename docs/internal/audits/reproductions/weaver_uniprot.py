"""Read-only offline reproductions for WV-UNIPROT-001 through 005.

Run with the isolated workspace Python. No biological network calls or writes.
This records observed behavior, not an implementation regression suite.
"""

import asyncio
from urllib.parse import parse_qs

import httpx
from braidworks.core import InMemoryStrandCache, Strand, StrandSet, compute_cache_key
from uniprot_weaver.backends.api import UniprotApiBackend
from uniprot_weaver.weaver import UniprotWeaver


async def main():
    def mapping(request):
        if request.url.path.endswith("/run"):
            target = parse_qs(request.content.decode())["to"][0]
            return httpx.Response(200, json={"jobId": target})
        if "/status/" in request.url.path:
            return httpx.Response(200, json={"jobStatus": "FINISHED"})
        source = "7157" if "Swiss-Prot" in request.url.path else "P04637"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"from": source, "to": "P99999"},
                    {"from": source, "to": "P04637"},
                    {"from": source, "to": "P04637"},
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(mapping)
    ) as client:
        backend = UniprotApiBackend(client=client)
        records = await backend.fetch(
            "map_to_accession",
            [{"gene.ncbi.id": "7157"}],
            requested_outputs=frozenset({"protein.uniprot.accession"}),
            groups_to_compute=frozenset(),
        )
        print("002 duplicate IDs/count:", records[0].values)
        weaver = UniprotWeaver({"api": backend})
        item = StrandSet.from_strands("p", [Strand("protein.uniprot.accession", "P04637")])
        cap = weaver.MANIFEST.capability("map_from_accession")
        result = await weaver.execute(
            "map_from_accession", item, requested_outputs=frozenset({"gene.ncbi.id"}), backend="api"
        )
        key = compute_cache_key(
            cap,
            item,
            weaver_id="uniprot",
            weaver_version=weaver.MANIFEST.version,
            backend="api",
            backend_fingerprint=weaver.backend_fingerprint("api"),
        )
        cache = InMemoryStrandCache()
        cache.put(key, result)
        hit = cache.get(key, cap.triggered_groups(frozenset({"pdb.id"})))
        print("003 PDB cache hit:", hit is not None, "available:", [s.type_id for s in hit.strands])
        count = await weaver.execute(
            "map_from_accession",
            item,
            requested_outputs=frozenset({"protein.uniprot.mapping.count"}),
            backend="api",
        )
        print("003 count-only:", count.status.value)

    def search(request):
        query = request.url.params["query"]
        exact = "accession:A0A024RBG1" in query
        reviewed = "reviewed:true" in query
        rows = (
            []
            if exact and reviewed
            else [
                {
                    "primaryAccession": "P99999" if reviewed else "A0A024RBG1",
                    "annotationScore": 5,
                    "entryType": "UniProtKB reviewed (Swiss-Prot)"
                    if reviewed
                    else "UniProtKB unreviewed (TrEMBL)",
                }
            ]
        )
        return httpx.Response(200, json={"results": rows})

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(search)
    ) as client:
        records = await UniprotApiBackend(client=client).fetch(
            "resolve_protein",
            [{"protein.query": "A0A024RBG1"}],
            requested_outputs=frozenset({"protein.uniprot.accession"}),
            groups_to_compute=frozenset(),
        )
        print("001 exact accession overridden:", records[0].values)

    for label, body, status in [
        ("invalid JSON", b"invalid", 200),
        ("null entry", b'{"results":[null]}', 200),
        ("404", b"{}", 404),
        ("400", b"{}", 400),
    ]:
        async with httpx.AsyncClient(
            base_url="https://fixture",
            transport=httpx.MockTransport(
                lambda request, status=status, body=body: httpx.Response(status, content=body)
            ),
        ) as client:
            try:
                result = await UniprotApiBackend(client=client).fetch(
                    "resolve_protein",
                    [{"protein.query": "P04637"}],
                    requested_outputs=frozenset({"protein.uniprot.accession"}),
                    groups_to_compute=frozenset(),
                )
                print("004/005", label, "error value:", bool(result[0].error))
            except Exception as exc:  # noqa: BLE001 - audit records escaped exception types
                print("004", label, "escaped:", type(exc).__name__)


if __name__ == "__main__":
    asyncio.run(main())
