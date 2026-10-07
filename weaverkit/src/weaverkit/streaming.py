"""Bounded progress streaming with reliable terminal delivery and owned task cleanup."""

import asyncio
import json
import logging
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from braidworks.core.exceptions import BraidworksError

_LOG = logging.getLogger(__name__)


async def query_events(
    execute: Callable[[Callable[[dict], None]], Awaitable[dict]], *, progress_capacity: int = 32
) -> AsyncIterator[dict[str, Any]]:
    """Own one execution task; coalesce oldest progress when consumers lag.

    Only progress occupies the bounded queue. Completion/errors are emitted directly
    after draining it, so capacity cannot discard a terminal event. Closing the iterator
    cancels and joins execution. Already-running synchronous worker threads may finish.
    """
    if type(progress_capacity) is not int or progress_capacity < 1:
        raise ValueError("progress_capacity must be a positive integer")
    queue = asyncio.Queue(maxsize=progress_capacity)

    def progress(event):
        if queue.full():
            queue.get_nowait()
        queue.put_nowait({"event": "wave", **event})

    task = None
    try:
        # Calling execute can itself reject input before returning an awaitable.
        task = asyncio.create_task(execute(progress))
        while not (task.done() and queue.empty()):
            try:
                yield await asyncio.wait_for(queue.get(), timeout=0.1)
            except TimeoutError:
                continue
        yield {**await task, "event": "done"}
    except (ValueError, BraidworksError, OSError, sqlite3.Error, KeyError) as exc:
        yield {"event": "error", "error": str(exc)}
    except Exception:  # noqa: BLE001 - preserve server traceback at the transport boundary
        _LOG.exception("Unexpected query stream failure")
        yield {"event": "error", "error": "Unexpected execution failure; see server log"}
    finally:
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def sse_events(execute, *, progress_capacity=32) -> AsyncIterator[str]:
    events = query_events(execute, progress_capacity=progress_capacity)
    try:
        async for event in events:
            yield f"data: {json.dumps(event, ensure_ascii=False, allow_nan=False)}\n\n"
    finally:
        await events.aclose()
