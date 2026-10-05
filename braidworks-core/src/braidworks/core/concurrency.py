"""Bounded, ordered async work for sources without a suitable bulk operation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import cast


async def map_bounded[T, R](
    items: Sequence[T],
    operation: Callable[[T], Awaitable[R]],
    *,
    limit: int = 4,
) -> list[R]:
    """Map with at most ``limit`` workers, retaining input order.

    This bounds concurrent operations, not HTTP requests per second. Operations
    should return per-item failures as values. An unexpected exception cancels
    and joins sibling workers before propagating the original exception.
    """
    if limit < 1:
        raise ValueError("concurrency limit must be positive")
    results: list[R | None] = [None] * len(items)
    pending = iter(enumerate(items))

    async def worker() -> None:
        for index, item in pending:
            results[index] = await operation(item)

    tasks = [asyncio.create_task(worker()) for _ in range(min(limit, len(items)))]
    try:
        await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return cast(list[R], results)
