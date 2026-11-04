"""Shared durable execution lifecycle, independent of CLI/browser presentation."""

import asyncio
import math
from collections.abc import Callable

from .cache import StrandCache
from .query import PreparedQuery
from .query_state import continue_query, start_query
from .registry import BraidRegistry
from .run_store import RunCheckpoint, RunConflict, RunDefinition, RunStore


async def start_run(
    registry: BraidRegistry,
    prepared: PreparedQuery,
    store: RunStore,
    *,
    run_id: str | None = None,
    worker_identity: dict | None = None,
    cache: StrandCache | None = None,
    on_event: Callable | None = None,
    on_saved: Callable[[RunCheckpoint], None] | None = None,
    lease_seconds: float = 60,
) -> RunCheckpoint:
    """Create then execute an explicit durable run; memory remains the default cache."""
    _validate_lease(lease_seconds)
    definition = RunDefinition.capture(registry, prepared, worker_identity=worker_identity)
    checkpoint = store.create(definition, start_query(prepared), run_id=run_id)
    if on_saved:
        on_saved(checkpoint)
    return await continue_run(
        registry,
        store,
        checkpoint.run_id,
        worker_identity=worker_identity,
        cache=cache,
        on_event=on_event,
        on_saved=on_saved,
        lease_seconds=lease_seconds,
    )


def _validate_lease(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("lease_seconds must be finite and positive")


async def continue_run(
    registry: BraidRegistry,
    store: RunStore,
    run_id: str,
    *,
    worker_identity: dict | None = None,
    expected_prepared: PreparedQuery | None = None,
    cache: StrandCache | None = None,
    on_event: Callable | None = None,
    on_saved: Callable[[RunCheckpoint], None] | None = None,
    lease_seconds: float = 60,
    decisions: tuple = (),
) -> RunCheckpoint:
    """Validate, claim and continue; interruption preserves the last applied snapshot.

    Completed/review queries return saved observations unless explicit ReviewDecision
    values are supplied. Choices resume only saved branches/phases, retaining the
    original policy for future results and the original source observation in history.
    """
    _validate_lease(lease_seconds)
    checkpoint = store.load(run_id)
    checkpoint.definition.validate(registry, worker_identity=worker_identity)
    if expected_prepared is not None and (
        expected_prepared.to_json() != checkpoint.definition.prepared.to_json()
    ):
        raise RunConflict("Resume query/options differ from the saved definition")
    reviewed = None
    if decisions:
        from .review import apply_review_decisions

        reviewed = apply_review_decisions(registry, checkpoint.state, decisions)
    if checkpoint.status in ("complete", "review") and checkpoint.state.done and not decisions:
        return checkpoint
    checkpoint = store.claim(run_id, revision=checkpoint.revision, lease_seconds=lease_seconds)
    execution = renewal = None

    def save(state):
        nonlocal checkpoint
        checkpoint.definition.validate(registry, worker_identity=worker_identity)
        checkpoint = store.save(run_id, state, revision=checkpoint.revision, owner=checkpoint.owner)
        if on_saved:
            on_saved(checkpoint)

    async def renew():
        nonlocal checkpoint
        while True:
            await asyncio.sleep(lease_seconds / 3)
            checkpoint = store.renew(
                run_id,
                revision=checkpoint.revision,
                owner=checkpoint.owner,
                lease_seconds=lease_seconds,
            )

    try:
        checkpoint.definition.validate(registry, worker_identity=worker_identity)
        state = reviewed if reviewed is not None else checkpoint.state
        execution = asyncio.create_task(
            continue_query(registry, state, cache=cache, on_event=on_event, on_checkpoint=save)
        )
        renewal = asyncio.create_task(renew())
        done, _ = await asyncio.wait((execution, renewal), return_when=asyncio.FIRST_COMPLETED)
        if renewal in done:
            await renewal  # Failure must stop a process that can no longer save.
            raise RunConflict("Lease renewal stopped unexpectedly")
        await execution
        checkpoint.definition.validate(registry, worker_identity=worker_identity)
        checkpoint = store.finish(
            run_id, state, revision=checkpoint.revision, owner=checkpoint.owner
        )
        if on_saved:
            on_saved(checkpoint)
        return checkpoint
    except BaseException:
        # Never serialize the in-flight mutable state. release() retains the last save.
        try:
            store.release(run_id, revision=checkpoint.revision, owner=checkpoint.owner)
        except RunConflict:
            pass  # Expired/stolen ownership must not overwrite the new owner's snapshot.
        raise
    finally:
        tasks = [task for task in (execution, renewal) if task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
