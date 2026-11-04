"""Request pacing counts redirects, preserves hooks, and isolates async job budgets."""

import asyncio

import httpx
import pytest
from braidworks.core.http_pacing import PacedHTTPClient, request_budget


async def test_redirects_and_shared_clients_charge_once_per_http_request():
    charges = []
    requests = []

    async def existing_hook(request):
        requests.append(str(request.url))

    async def charge(weaver, backend):
        charges.append((weaver, backend))

    def respond(request):
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "/data"})
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
        base_url="https://fixture.test",
        follow_redirects=True,
        event_hooks={"request": [existing_hook]},
    ) as client:
        first = PacedHTTPClient(client, "first")
        second = PacedHTTPClient(client, "second")
        with request_budget(charge):
            await first.get("/redirect")
            await second.post("/data")
            async with first.stream("GET", "/data") as response:
                assert response.status_code == 200
        assert charges == [("first", "api"), ("first", "api"), ("second", "api"), ("first", "api")]
        assert len(requests) == 4
        assert len(client.event_hooks["request"]) == 2


async def test_concurrent_jobs_keep_their_own_budgets_and_restore_after_failure():
    charges = {"one": 0, "two": 0}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200))
    ) as client:
        paced = PacedHTTPClient(client, "fixture")

        async def job(name):
            async def charge(*_):
                charges[name] += 1
                await asyncio.sleep(0)

            with request_budget(charge):
                await paced.get("https://fixture.test/page1")
                await paced.get("https://fixture.test/page2")

        await asyncio.gather(job("one"), job("two"))
        assert charges == {"one": 2, "two": 2}
        await paced.get("https://fixture.test/no-job")
        assert charges == {"one": 2, "two": 2}


async def test_local_pacing_is_shared_across_clients(monkeypatch):
    from braidworks.core import http_pacing

    clock = [0.0]
    monkeypatch.setattr(http_pacing, "monotonic", lambda: clock[0])
    monkeypatch.setattr(http_pacing, "_local", {})
    monkeypatch.setenv("BRAIDWORKS_RATE_LIMITS", "fixture:api=2")

    async def advance(seconds):
        clock[0] += seconds

    monkeypatch.setattr(http_pacing.asyncio, "sleep", advance)
    arrivals = []

    def respond(_):
        arrivals.append(clock[0])
        return httpx.Response(200)

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(respond)) as first,
        httpx.AsyncClient(transport=httpx.MockTransport(respond)) as second,
    ):
        for i in range(5):
            await PacedHTTPClient(first if i % 2 else second, "fixture").get(
                "https://fixture.test/data"
            )
    assert arrivals == [0, 0.5, 1, 1.5, 2]


async def test_cancellation_while_waiting_sends_no_extra_request(monkeypatch):
    started = asyncio.Event()
    charges = 0
    sent = []

    async def charge(*_):
        nonlocal charges
        charges += 1
        if charges > 1:
            started.set()
            await asyncio.Event().wait()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: sent.append(req) or httpx.Response(200))
    ) as client:
        paced = PacedHTTPClient(client, "fixture")
        with request_budget(charge):
            await paced.get("https://fixture.test/first")
            task = asyncio.create_task(paced.get("https://fixture.test/second"))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert len(sent) == 1


def test_local_budget_survives_separate_event_loops(monkeypatch):
    from braidworks.core import http_pacing

    clock = [0.0]
    monkeypatch.setattr(http_pacing, "monotonic", lambda: clock[0])
    monkeypatch.setattr(http_pacing, "_local", {})
    monkeypatch.setenv("BRAIDWORKS_RATE_LIMITS", "fixture:api=2")

    async def advance(seconds):
        clock[0] += seconds

    monkeypatch.setattr(http_pacing.asyncio, "sleep", advance)
    arrivals = []

    async def query():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: arrivals.append(clock[0]) or httpx.Response(200)
            )
        ) as client:
            await PacedHTTPClient(client, "fixture").get("https://fixture.test/data")

    for _ in range(3):
        asyncio.run(query())
    assert arrivals == [0, 0.5, 1]


@pytest.mark.parametrize(
    "configured,expected", [(None, [0, 0.5, 1]), ("fixture=4", [0, 0.25, 0.5])]
)
async def test_source_default_rate_and_explicit_environment_override(
    monkeypatch, configured, expected
):
    from braidworks.core import http_pacing

    clock = [0.0]
    monkeypatch.setattr(http_pacing, "monotonic", lambda: clock[0])
    monkeypatch.setattr(http_pacing, "_local", {})
    monkeypatch.delenv("BRAIDWORKS_RATE_LIMITS", raising=False)
    if configured:
        monkeypatch.setenv("BRAIDWORKS_RATE_LIMITS", configured)

    async def advance(seconds):
        clock[0] += seconds

    monkeypatch.setattr(http_pacing.asyncio, "sleep", advance)
    arrivals = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: arrivals.append(clock[0]) or httpx.Response(200))
    ) as client:
        paced = PacedHTTPClient(client, "fixture", default_rate=2)
        for _ in range(3):
            await paced.get("https://source/page")
    assert arrivals == expected


async def test_executor_budget_takes_precedence_over_source_default(monkeypatch):
    monkeypatch.delenv("BRAIDWORKS_RATE_LIMITS", raising=False)
    charges = []

    async def charge(*target):
        charges.append(target)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200))
    ) as client:
        with request_budget(charge):
            for _ in range(3):
                await PacedHTTPClient(client, "fixture", default_rate=0.001).get(
                    "https://source/page"
                )
    assert charges == [("fixture", "api")] * 3


@pytest.mark.parametrize("rate", [True, 0, -1, float("nan"), float("inf")])
def test_invalid_source_default_rate_is_rejected(rate):
    with pytest.raises(ValueError, match="default request rate"):
        PacedHTTPClient(None, "fixture", default_rate=rate)
