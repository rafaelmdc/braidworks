"""Source recommendations are explicit and correlation stays bounded and echoed."""

import httpx
from string_weaver.backends.api import StringApiBackend


async def test_mapping_explicitly_requests_echo_query_and_caller_identity():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["echo_query"] == "1"
        assert request.url.params["caller_identity"] == "braidworks"
        return httpx.Response(
            200,
            json=[
                {"queryItem": "P04637", "queryIndex": 0, "stringId": "9606.tp53"},
                {"queryItem": "Q00987", "queryIndex": 1, "stringId": "9606.mdm2"},
            ],
        )

    async with httpx.AsyncClient(
        base_url="https://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        mapped, errors = await StringApiBackend(client=client)._string_ids(["P04637", "Q00987"])
    assert mapped == {"P04637": "9606.tp53", "Q00987": "9606.mdm2"} and not errors
    assert len(calls) == 1


def test_provider_default_rate_is_one_request_per_second():
    backend = StringApiBackend()
    paced = backend._http()
    assert paced._target == ("string", "api", 1.0)
