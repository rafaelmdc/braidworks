"""Concurrent source work is bounded, ordered, and leaves no work running on failure."""

import asyncio

import pytest
from braidworks.core.concurrency import map_bounded


async def test_bounded_workers_preserve_input_order_with_out_of_order_completion():
    active = peak = 0
    finished = []

    async def operation(value):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01 if value == 0 else 0.001)
        finished.append(value)
        active -= 1
        return value * 2

    assert await map_bounded(list(range(8)), operation, limit=2) == list(range(0, 16, 2))
    assert peak == 2 and active == 0
    assert finished[0] != 0


async def test_unexpected_failure_cancels_sibling_work_before_returning():
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def operation(value):
        if value == 0:
            await started.wait()
            raise ValueError("structural error")
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            stopped.set()

    with pytest.raises(ValueError, match="structural error"):
        await map_bounded([0, 1], operation, limit=2)
    assert stopped.is_set()


async def test_empty_input_and_invalid_limit():
    async def operation(value):
        raise AssertionError("empty input must not call the operation")

    assert await map_bounded([], operation, limit=2) == []
    with pytest.raises(ValueError, match="positive"):
        await map_bounded([], operation, limit=0)
