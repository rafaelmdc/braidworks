"""Resource ownership is explicit and cleanup preserves borrowed transports."""

import asyncio

import httpx
import pytest
from braidworks.core.exceptions import BackendConfigurationError
from braidworks.core.lifecycle import HTTPClientLifecycle, close_backends, reject_unknown_options


class Adapter(HTTPClientLifecycle):
    def __init__(self, client=None):
        self._configure_client(client, "https://source.example")

    def http(self):
        self._ensure_open()
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url)
        return self._client


async def test_owned_client_closes_once_and_is_not_recreated(monkeypatch):
    adapter = Adapter()
    client = adapter.http()
    calls = []
    original = client.aclose

    async def close():
        calls.append(1)
        await original()

    monkeypatch.setattr(client, "aclose", close)
    await close_backends([adapter, adapter])
    await adapter.aclose()
    assert calls == [1] and client.is_closed
    with pytest.raises(BackendConfigurationError, match="closed"):
        adapter.http()


async def test_borrowed_client_survives_adapter_close():
    async with httpx.AsyncClient(
        base_url="https://borrowed.example",
        transport=httpx.MockTransport(lambda _: httpx.Response(200)),
    ) as client:
        adapter = Adapter(client)
        assert adapter._base_url == "https://borrowed.example"
        await adapter.aclose()
        assert (await client.get("/probe")).status_code == 200


async def test_uninitialized_owned_client_close_is_lazy():
    adapter = Adapter()
    await adapter.aclose()
    assert adapter._client is None


async def test_cleanup_attempts_other_adapters_when_one_close_fails():
    called = []

    class Resource:
        async def aclose(self):
            called.append(1)
            raise OSError("close failed")

    with pytest.raises(ExceptionGroup):
        await close_backends([Resource(), Resource()])
    assert len(called) == 2


async def test_cleanup_does_not_swallow_cancellation():
    class Resource:
        async def aclose(self):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await close_backends([Resource()])


def test_unknown_configuration_does_not_echo_values():
    reject_unknown_options({})
    with pytest.raises(BackendConfigurationError, match="misspelled") as error:
        reject_unknown_options({"misspelled": "secret-value"})
    assert "secret-value" not in str(error.value)


async def test_relative_or_closed_injected_clients_are_rejected():
    async with httpx.AsyncClient(base_url="/") as client:
        with pytest.raises(BackendConfigurationError, match="absolute"):
            Adapter(client)
    client = httpx.AsyncClient(base_url="https://source.example")
    await client.aclose()
    with pytest.raises(BackendConfigurationError, match="already closed"):
        Adapter(client)
