"""Durable query snapshots with compare-and-swap revisions and bounded owner leases.

A lease grants permission to save, not a lock held across source I/O. Interrupted
unapplied waves may repeat reads; fingerprints do not freeze remote providers.
"""

from __future__ import annotations

import math
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .archive import begin_archive
from .cache_codec import canonical_json, decode_json
from .query import PreparedQuery
from .query_state import QueryExecutionState
from .registry import BraidRegistry
from .sqlite import connection_scope, transaction


class RunConflict(ValueError):
    """Ownership, revision or immutable run identity no longer matches."""


@dataclass(frozen=True)
class RunDefinition:
    prepared: PreparedQuery
    sources: list[dict[str, Any]]
    worker_identity: dict[str, Any]

    @classmethod
    def capture(
        cls, registry: BraidRegistry, prepared: PreparedQuery, *, worker_identity=None
    ) -> RunDefinition:
        # Capture the whole registry: rerouting can use sources outside the initial plan.
        sources = begin_archive(
            list(prepared.request.inputs), registry, options={}, plans=[], effective_params={}
        )["sources"]
        return cls.from_json(
            {
                "version": 1,
                "prepared": prepared.to_json(),
                "sources": sources,
                "worker_identity": worker_identity or {},
            }
        )

    def to_json(self) -> dict[str, Any]:
        return decode_json(
            canonical_json(
                {
                    "version": 1,
                    "prepared": self.prepared.to_json(),
                    "sources": self.sources,
                    "worker_identity": self.worker_identity,
                }
            )
        )

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> RunDefinition:
        if data.get("version") != 1:
            raise ValueError("Unsupported run definition version")
        data = decode_json(canonical_json(data))
        if not isinstance(data["sources"], list) or not isinstance(data["worker_identity"], dict):
            raise TypeError("Invalid run identity")
        return cls(
            PreparedQuery.from_json(data["prepared"]), data["sources"], data["worker_identity"]
        )

    def validate(self, registry: BraidRegistry, *, worker_identity=None) -> None:
        current = self.capture(registry, self.prepared, worker_identity=worker_identity)
        if current.to_json() != self.to_json():
            raise RunConflict("Run source, manifest or worker identity changed; start a new run")


@dataclass(frozen=True)
class RunCheckpoint:
    run_id: str
    definition: RunDefinition
    state: QueryExecutionState
    revision: int
    status: str
    owner: str | None
    lease_until: float | None
    created_at: float
    updated_at: float

    def to_json(self) -> dict[str, Any]:
        return {
            "version": 1,
            "run_id": self.run_id,
            "definition": self.definition.to_json(),
            "state": self.state.to_json(),
            "revision": self.revision,
            "status": self.status,
            "owner": self.owner,
            "lease_until": self.lease_until,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> RunCheckpoint:
        if data.get("version") != 1:
            raise ValueError("Unsupported run checkpoint version")
        data = decode_json(canonical_json(data))
        definition = RunDefinition.from_json(data["definition"])
        state = QueryExecutionState.from_json(data["state"])
        _validate_state(definition, state)
        if type(data["revision"]) is not int or data["revision"] < 0:
            raise ValueError("Invalid checkpoint revision")
        if data["status"] not in ("ready", "running", "paused", "review", "complete"):
            raise ValueError("Invalid run status")
        if (data["owner"] is None) != (data["lease_until"] is None):
            raise ValueError("Invalid lease ownership")
        if data["owner"] is not None and not isinstance(data["owner"], str):
            raise ValueError("Invalid run owner")
        for key in ("created_at", "updated_at", "lease_until"):
            if data[key] is not None and (
                type(data[key]) not in (int, float) or not math.isfinite(data[key])
            ):
                raise ValueError("Invalid checkpoint timestamp")
        return cls(
            data["run_id"],
            definition,
            state,
            data["revision"],
            data["status"],
            data["owner"],
            data["lease_until"],
            data["created_at"],
            data["updated_at"],
        )


def _validate_state(definition: RunDefinition, state: QueryExecutionState) -> None:
    if canonical_json(definition.prepared.to_json()) != canonical_json(state.prepared.to_json()):
        raise RunConflict("Checkpoint query/options differ from the immutable run definition")
    if state.settings_override:
        raise RunConflict("Durable runs cannot override the saved query options")


class RunStore(Protocol):
    def create(
        self, definition: RunDefinition, state: QueryExecutionState, *, run_id: str | None = None
    ) -> RunCheckpoint: ...
    def load(self, run_id: str) -> RunCheckpoint: ...
    def claim(self, run_id: str, *, revision: int, lease_seconds: float = 60) -> RunCheckpoint: ...
    def renew(
        self, run_id: str, *, revision: int, owner: str, lease_seconds: float = 60
    ) -> RunCheckpoint: ...
    def save(
        self, run_id: str, state: QueryExecutionState, *, revision: int, owner: str
    ) -> RunCheckpoint: ...
    def finish(
        self, run_id: str, state: QueryExecutionState, *, revision: int, owner: str
    ) -> RunCheckpoint: ...
    def release(self, run_id: str, *, revision: int, owner: str) -> RunCheckpoint: ...


class SQLiteRunStore:
    """One complete versioned JSON snapshot per run, atomically replaced."""

    def __init__(
        self, path: str | Path, *, clock: Callable[[], float] = time.time, create: bool = True
    ):
        self.path = Path(path)
        self.clock = clock
        if not create:
            with connection_scope(self.path, readonly=True) as connection:
                self._schema(connection)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connection_scope(self.path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            with transaction(connection, immediate=True):
                present = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='run_store_meta'"
                ).fetchone()
                if not present:
                    if connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='query_runs'"
                    ).fetchone():
                        raise ValueError("Run store metadata missing; refusing to overwrite")
                    connection.execute("CREATE TABLE run_store_meta (version INTEGER NOT NULL)")
                    connection.execute("INSERT INTO run_store_meta VALUES (1)")
                    connection.execute(
                        "CREATE TABLE query_runs (run_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL)"
                    )
                self._schema(connection)

    @staticmethod
    def _schema(connection):
        rows = connection.execute("SELECT version FROM run_store_meta").fetchall()
        if len(rows) != 1 or rows[0][0] != 1:
            raise ValueError("Unsupported run store schema; preserve the database for migration")

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Run clock must return a finite timestamp")
        return value

    @staticmethod
    def _read(connection, run_id):
        row = connection.execute(
            "SELECT snapshot FROM query_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(run_id)
        checkpoint = RunCheckpoint.from_json(decode_json(row[0]))
        if checkpoint.run_id != run_id:
            raise ValueError("Checkpoint run identity mismatch")
        return checkpoint

    @staticmethod
    def _write(connection, checkpoint):
        payload = canonical_json(checkpoint.to_json())
        RunCheckpoint.from_json(decode_json(payload))
        connection.execute(
            "UPDATE query_runs SET snapshot=? WHERE run_id=?",
            (payload, checkpoint.run_id),
        )

    def create(self, definition, state, *, run_id=None):
        _validate_state(definition, state)
        run_id = str(uuid.uuid4()) if run_id is None else run_id
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id must be a nonempty string")
        now = self._now()
        checkpoint = RunCheckpoint(run_id, definition, state, 0, "ready", None, None, now, now)
        payload = canonical_json(checkpoint.to_json())
        RunCheckpoint.from_json(decode_json(payload))
        with connection_scope(self.path) as connection, transaction(connection, immediate=True):
            self._schema(connection)
            if connection.execute("SELECT 1 FROM query_runs WHERE run_id=?", (run_id,)).fetchone():
                raise RunConflict("Run already exists")
            connection.execute("INSERT INTO query_runs VALUES (?, ?)", (run_id, payload))
        return RunCheckpoint.from_json(decode_json(payload))

    def load(self, run_id):
        with connection_scope(self.path, readonly=True) as connection:
            self._schema(connection)
            return self._read(connection, run_id)

    def list(self) -> list[RunCheckpoint]:
        with connection_scope(self.path, readonly=True) as connection:
            self._schema(connection)
            rows = connection.execute("SELECT run_id FROM query_runs ORDER BY run_id").fetchall()
            return [self._read(connection, row[0]) for row in rows]

    def _change(self, run_id, revision, owner, operation, *, state=None, lease_seconds=None):
        if type(revision) is not int or revision < 0:
            raise ValueError("revision must be a nonnegative integer")
        if lease_seconds is not None and (
            type(lease_seconds) not in (int, float)
            or not math.isfinite(lease_seconds)
            or lease_seconds <= 0
        ):
            raise ValueError("lease_seconds must be finite and positive")
        with connection_scope(self.path) as connection, transaction(connection, immediate=True):
            self._schema(connection)
            old = self._read(connection, run_id)
            now = self._now()  # Evaluate after acquiring the writer lock.
            if old.revision != revision:
                raise RunConflict("Stale checkpoint revision")
            token, deadline, status = old.owner, old.lease_until, old.status
            if operation == "claim":
                if status == "complete":
                    raise RunConflict("Run is already complete")
                if token is not None and deadline > now:
                    raise RunConflict("Run has a live owner")
                token, deadline, status = str(uuid.uuid4()), now + lease_seconds, "running"
            else:
                if not owner or token != owner or deadline is None or deadline <= now:
                    raise RunConflict("Run ownership expired or changed")
                if operation == "renew":
                    deadline = now + lease_seconds
                elif operation == "release":
                    token, deadline, status = None, None, "paused"
                elif operation == "finish":
                    if not state.done:
                        raise RunConflict("Cannot finish an incomplete query")
                    token, deadline = None, None
                    status = "review" if state.result.review_queue else "complete"
            if deadline is not None and not math.isfinite(deadline):
                raise ValueError("Lease deadline must be finite")
            state = old.state if state is None else state
            _validate_state(old.definition, state)
            new = RunCheckpoint(
                run_id,
                old.definition,
                state,
                revision + 1,
                status,
                token,
                deadline,
                old.created_at,
                now,
            )
            self._write(connection, new)
            payload = canonical_json(new.to_json())
        return RunCheckpoint.from_json(decode_json(payload))

    def claim(self, run_id, *, revision, lease_seconds=60):
        return self._change(run_id, revision, None, "claim", lease_seconds=lease_seconds)

    def renew(self, run_id, *, revision, owner, lease_seconds=60):
        return self._change(run_id, revision, owner, "renew", lease_seconds=lease_seconds)

    def save(self, run_id, state, *, revision, owner):
        return self._change(run_id, revision, owner, "save", state=state)

    def finish(self, run_id, state, *, revision, owner):
        return self._change(run_id, revision, owner, "finish", state=state)

    def release(self, run_id, *, revision, owner):
        return self._change(run_id, revision, owner, "release")


def run_status(checkpoint: RunCheckpoint) -> dict[str, Any]:
    """Human-interface data without exposing the opaque owner token or runtime handles."""
    return decode_json(
        canonical_json(
            {
                "run_id": checkpoint.run_id,
                "revision": checkpoint.revision,
                "status": checkpoint.status,
                "created_at": checkpoint.created_at,
                "updated_at": checkpoint.updated_at,
                "lease_until": checkpoint.lease_until,
                "inputs": len(checkpoint.definition.prepared.request.inputs),
                "options": checkpoint.definition.prepared.request.options.to_json(),
                "targets": sorted(checkpoint.definition.prepared.request.targets),
                "reviews": [item.to_json() for item in checkpoint.state.result.review_queue],
                "decisions": checkpoint.state.review_decisions,
                "pending_continuations": len(checkpoint.state.review_continuations),
            }
        )
    )
