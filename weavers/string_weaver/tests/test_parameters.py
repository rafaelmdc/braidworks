"""Per-query scope is validated before network work and retained in evidence."""

import httpx
import pytest
from string_weaver.backends.api import StringApiBackend
from string_weaver.fixture import _handler


async def test_scope_applies_to_both_bulk_stages_and_retains_units():
    calls = []

    def handler(request):
        calls.append(request)
        return _handler(request)

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        backend = StringApiBackend(client=client)
        queries = [{"protein.uniprot.accession": "P04637"}] * 3
        records = await backend.fetch(
            "list_interactions",
            queries,
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"summary"}),
            params={"species": 9606, "required_score": 700, "network_type": "physical"},
        )
        assert len(calls) == 2
        assert all(call.url.params["species"] == "9606" for call in calls)
        assert "required_score" not in calls[0].url.params
        assert calls[1].url.params["required_score"] == "700"
        assert calls[1].url.params["network_type"] == "physical"
        assert all(record.found for record in records)
        scope = records[0].values["protein.interaction.coverage"]
        assert scope["required_score_scale"] == [0, 1000]
        assert scope["score_scale"] == [0, 1]
        assert scope["complete"] is None
        mismatch = await backend.fetch(
            "list_interactions",
            queries[:1],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
            params={"species": 10090},
        )
        assert mismatch[0].error and not mismatch[0].found
        assert len(calls) == 3  # conflicting mapping never reaches partners


@pytest.mark.parametrize(
    "params",
    [
        {"required_score": -1},
        {"required_score": 1001},
        {"required_score": True},
        {"species": 0},
        {"network_type": "regulatory"},
    ],
)
async def test_invalid_scope_performs_no_requests(params):
    def handler(request):
        pytest.fail("invalid scope must not request upstream data")

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        result = await StringApiBackend(client=client).fetch(
            "list_interactions",
            [{"protein.uniprot.accession": "P04637"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset(),
            params=params,
        )
        assert result[0].error
