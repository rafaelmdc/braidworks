"""Real SQLite ownership, recovery, atomicity and immutable-definition contracts."""

import json
import multiprocessing
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from braidworks.core import QueryRequest, prepare_query
from braidworks.core.query_state import continue_query, start_query
from braidworks.core.run_store import RunCheckpoint, RunConflict, RunDefinition, SQLiteRunStore
from test_query import _input, _registry


@pytest.fixture
def run(tmp_path):
    registry = _registry()
    prepared = prepare_query(
        registry, QueryRequest((_input("a", 1), _input("a", 1)), frozenset({"output.value"}))
    )
    clock = [100.0]
    store = SQLiteRunStore(tmp_path / "runs.sqlite", clock=lambda: clock[0])
    checkpoint = store.create(RunDefinition.capture(registry, prepared), start_query(prepared))
    return store, checkpoint, clock, registry


def test_reopen_roundtrip_and_duplicate_rows(run):
    store, checkpoint, _, registry = run
    loaded = SQLiteRunStore(store.path).load(checkpoint.run_id)
    assert loaded.to_json() == checkpoint.to_json()
    assert (
        RunCheckpoint.from_json(json.loads(json.dumps(loaded.to_json()))).to_json()
        == loaded.to_json()
    )
    assert len({ss.execution_key for ss in loaded.state.inputs}) == 2
    loaded.definition.validate(registry)
    assert [cp.run_id for cp in store.list()] == [checkpoint.run_id]
    with pytest.raises(RunConflict, match="already exists"):
        store.create(checkpoint.definition, checkpoint.state, run_id=checkpoint.run_id)


def test_live_owner_stale_revision_and_wrong_token(run):
    store, original, _, _ = run
    claimed = store.claim(original.run_id, revision=0)
    assert claimed.revision == 1
    for action in (
        lambda: store.claim(original.run_id, revision=1),
        lambda: store.save(original.run_id, original.state, revision=0, owner=claimed.owner),
        lambda: store.save(original.run_id, original.state, revision=1, owner="another"),
    ):
        with pytest.raises(RunConflict):
            action()
    assert store.load(original.run_id).to_json() == claimed.to_json()


def test_expired_owner_recovery_renew_and_release(run):
    store, original, clock, _ = run
    claimed = store.claim(original.run_id, revision=0, lease_seconds=10)
    clock[0] = 105
    renewed = store.renew(original.run_id, revision=1, owner=claimed.owner, lease_seconds=10)
    assert renewed.lease_until == 115
    clock[0] = 115
    with pytest.raises(RunConflict, match="expired"):
        store.save(original.run_id, original.state, revision=2, owner=claimed.owner)
    recovered = store.claim(original.run_id, revision=2)
    assert recovered.owner != claimed.owner
    with pytest.raises(RunConflict):
        store.release(original.run_id, revision=3, owner=claimed.owner)
    released = store.release(original.run_id, revision=3, owner=recovered.owner)
    assert released.status == "paused" and released.owner is None
    assert store.claim(original.run_id, revision=4).owner


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan"), True])
def test_invalid_lease_does_not_change_snapshot(run, duration):
    store, original, _, _ = run
    with pytest.raises(ValueError):
        store.claim(original.run_id, revision=0, lease_seconds=duration)
    assert store.load(original.run_id).to_json() == original.to_json()


def test_competing_connections_only_one_claims(run):
    store, original, clock, _ = run

    def claim(_):
        other = SQLiteRunStore(store.path, clock=lambda: clock[0])
        try:
            return other.claim(original.run_id, revision=0)
        except RunConflict:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(claim, range(4)))
    assert sum(cp is not None for cp in results) == 1
    assert store.load(original.run_id).revision == 1


def _claim_then_exit(path, run_id):
    store = SQLiteRunStore(path, clock=lambda: 100)
    store.claim(run_id, revision=0, lease_seconds=10)


def test_exited_process_lease_recovers_after_deadline(run):
    store, original, clock, _ = run
    process = multiprocessing.get_context("spawn").Process(
        target=_claim_then_exit, args=(store.path, original.run_id)
    )
    process.start()
    process.join(timeout=20)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail("Claim process did not exit")
    assert process.exitcode == 0
    with pytest.raises(RunConflict, match="live owner"):
        store.claim(original.run_id, revision=1)
    clock[0] = 110
    assert store.claim(original.run_id, revision=1).revision == 2


def test_write_failure_rolls_back_snapshot_and_revision(run):
    store, original, _, _ = run
    claimed = store.claim(original.run_id, revision=0)
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_save BEFORE UPDATE ON query_runs "
            "BEGIN SELECT RAISE(ABORT, 'injected write failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        store.save(original.run_id, original.state, revision=1, owner=claimed.owner)
    assert store.load(original.run_id).to_json() == claimed.to_json()


def test_changed_options_and_worker_identity_reject(run):
    store, original, _, registry = run
    claimed = store.claim(original.run_id, revision=0)
    changed = original.state.to_json()
    changed["prepared"]["request"]["options"]["max_expansion"] += 1
    from braidworks.core.query_state import QueryExecutionState

    with pytest.raises(RunConflict, match="query/options"):
        store.save(
            original.run_id, QueryExecutionState.from_json(changed), revision=1, owner=claimed.owner
        )
    with pytest.raises(RunConflict, match="worker"):
        original.definition.validate(registry, worker_identity={"manifest": "different"})
    registry.get_weaver("a").backend_fingerprint = lambda backend: "changed-generation"
    with pytest.raises(RunConflict, match="source"):
        original.definition.validate(registry)
    assert store.load(original.run_id).to_json() == claimed.to_json()


async def test_saved_wave_continues_without_repeating_completed_work(run):
    store, original, _, registry = run
    claimed = store.claim(original.run_id, revision=0)
    checkpoints = []
    await continue_query(
        registry, original.state, on_checkpoint=lambda state: checkpoints.append(state.to_json())
    )
    from braidworks.core.query_state import QueryExecutionState

    state = QueryExecutionState.from_json(checkpoints[-1])
    saved = store.save(original.run_id, state, revision=1, owner=claimed.owner)
    calls = registry.get_weaver("a").batch_calls
    await continue_query(registry, SQLiteRunStore(store.path).load(original.run_id).state)
    assert registry.get_weaver("a").batch_calls == calls
    finished = store.finish(original.run_id, saved.state, revision=2, owner=claimed.owner)
    assert finished.status == "complete" and finished.owner is None
    with pytest.raises(RunConflict, match="complete"):
        store.claim(original.run_id, revision=3)


def test_cannot_finish_incomplete_query(run):
    store, original, _, _ = run
    claimed = store.claim(original.run_id, revision=0)
    with pytest.raises(RunConflict, match="incomplete"):
        store.finish(original.run_id, original.state, revision=1, owner=claimed.owner)


@pytest.mark.parametrize("corruption", ["schema", "json", "version", "identity"])
def test_corrupt_or_future_checkpoint_rejects(run, corruption):
    store, original, _, _ = run
    with sqlite3.connect(store.path) as connection:
        if corruption == "schema":
            connection.execute("UPDATE run_store_meta SET version=999")
        else:
            payload = original.to_json()
            if corruption == "version":
                payload["version"] = 999
            elif corruption == "identity":
                payload["run_id"] = "another"
            connection.execute(
                "UPDATE query_runs SET snapshot=?",
                ("{bad" if corruption == "json" else json.dumps(payload),),
            )
    with pytest.raises(ValueError):
        store.load(original.run_id)


def _uncommitted_write(path, run_id, ready):
    connection = sqlite3.connect(path)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("UPDATE query_runs SET snapshot='incomplete' WHERE run_id=?", (run_id,))
    ready.send(True)
    # Parent kills us after the write is observable through the handshake.
    ready.recv()


def test_process_death_during_transaction_retains_previous_checkpoint(run):
    store, original, _, _ = run
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_uncommitted_write, args=(store.path, original.run_id, child))
    process.start()
    child.close()
    try:
        assert parent.poll(20), "Writer did not reach the transaction boundary"
        assert parent.recv() is True
        assert store.load(original.run_id).to_json() == original.to_json()
    finally:
        process.kill()
        process.join(timeout=20)
        parent.close()
    assert store.load(original.run_id).to_json() == original.to_json()
    assert store.claim(original.run_id, revision=0).revision == 1


def test_invalid_state_is_rejected_before_commit(run):
    store, original, _, _ = run
    claimed = store.claim(original.run_id, revision=0)
    original.state.phase = "invalid"
    with pytest.raises(ValueError, match="phase"):
        store.save(original.run_id, original.state, revision=1, owner=claimed.owner)
    assert store.load(original.run_id).to_json() == claimed.to_json()
