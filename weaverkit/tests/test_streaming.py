"""Streaming lifecycle tests with deterministic synchronization and bounded progress."""

import asyncio
import json

import pytest
from weaverkit.streaming import query_events, sse_events


async def test_slow_consumer_bounds_progress_and_keeps_terminal():
    started = asyncio.Event()
    release = asyncio.Event()

    async def execute(progress):
        progress({"wave": 0})
        started.set()
        await release.wait()
        for wave in range(1, 101):
            progress({"wave": wave})
        return {"ok": True, "rows": ["complete"]}

    events = query_events(execute, progress_capacity=3)
    first = await anext(events)
    assert first == {"event": "wave", "wave": 0}
    await started.wait()
    release.set()
    await asyncio.sleep(0)
    remaining = [event async for event in events]
    assert [event["wave"] for event in remaining[:-1]] == [98, 99, 100]
    assert remaining[-1] == {"event": "done", "ok": True, "rows": ["complete"]}


async def test_close_cancels_and_joins_execution():
    cancelled = asyncio.Event()

    async def execute(progress):
        progress({"wave": 0})
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    events = query_events(execute)
    assert (await anext(events))["event"] == "wave"
    await events.aclose()
    assert cancelled.is_set()


async def test_sse_close_also_closes_underlying_iterator():
    cancelled = asyncio.Event()

    async def execute(progress):
        progress({"wave": 0})
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    stream = sse_events(execute)
    assert json.loads((await anext(stream))[6:])["event"] == "wave"
    await stream.aclose()
    assert cancelled.is_set()


async def test_domain_error_follows_buffered_progress():
    async def execute(progress):
        progress({"wave": 1})
        raise ValueError("invalid parameter")

    events = [event async for event in query_events(execute)]
    assert [event["event"] for event in events] == ["wave", "error"]
    assert events[-1]["error"] == "invalid parameter"


async def test_unexpected_failure_keeps_traceback(caplog):
    async def execute(progress):
        raise RuntimeError("internal detail")

    events = [event async for event in query_events(execute)]
    assert events == [{"event": "error", "error": "Unexpected execution failure; see server log"}]
    assert "RuntimeError: internal detail" in caplog.text


async def test_synchronous_validation_failure_is_terminal():
    def execute(progress):
        raise ValueError("bad input")

    assert [event async for event in query_events(execute)] == [
        {"event": "error", "error": "bad input"}
    ]


@pytest.mark.parametrize("capacity", [0, -1, True])
async def test_invalid_capacity(capacity):
    with pytest.raises(ValueError):
        await anext(query_events(lambda progress: None, progress_capacity=capacity))


async def test_input_progress_retains_its_event_type():
    async def execute(progress):
        progress({"event": "progress", "input_count": 3, "completed_inputs": 2})
        return {"ok": True}

    events = [event async for event in query_events(execute)]
    assert events[0] == {"event": "progress", "input_count": 3, "completed_inputs": 2}
    assert events[-1]["event"] == "done"
