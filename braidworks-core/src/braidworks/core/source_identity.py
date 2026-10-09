"""Bind a local read session to an immutable artifact generation.

File stamps detect local replacement without hashing large dumps. Source packages
supply metadata from the same read transaction as the result. Legacy file stamps
are local generation guards, not portable content checksums.
"""

import hashlib
import json
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import BackendConfigurationError
from .sqlite import connection_scope


def artifact_stamp(path: str | Path) -> tuple[int, int, int, int]:
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


@dataclass(frozen=True)
class SourceIdentity:
    metadata: tuple[tuple[str, str], ...]
    artifacts: tuple[tuple[str, tuple[int, int, int, int]], ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "version": 1,
            "metadata": [list(item) for item in self.metadata],
            "artifacts": [[name, list(stamp)] for name, stamp in self.artifacts],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SourceIdentity":
        if data.get("version") != 1:
            raise ValueError("Unsupported source identity version")
        return cls(
            tuple((str(k), str(v)) for k, v in data["metadata"]),
            tuple((str(k), tuple(v)) for k, v in data["artifacts"]),
        )

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.to_json(), sort_keys=True, separators=(",", ":"))
        return "local-generation-" + hashlib.sha256(payload.encode()).hexdigest()


class SourceBinding:
    """One backend's expected generation; sessions own and close their readers."""

    def __init__(
        self,
        path: str | Path,
        metadata: Callable[[sqlite3.Connection], dict[str, str]],
        *,
        components: tuple[Path, ...] = (),
    ) -> None:
        self.path = Path(path)
        self._metadata = metadata
        self._components = components
        self._expected: SourceIdentity | None = None
        self._lock = threading.Lock()

    def _stamps(self) -> tuple[tuple[str, tuple[int, int, int, int]], ...]:
        paths = (self.path, self.path.with_name(self.path.name + "-wal"), *self._components)
        return tuple(
            (str(path.absolute()), artifact_stamp(path) if path.exists() else (0, 0, 0, 0))
            for path in paths
        )

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        before = self._stamps()
        with connection_scope(self.path, readonly=True) as connection:
            connection.execute("BEGIN")  # Metadata and rows share one SQLite snapshot.
            identity = SourceIdentity(tuple(sorted(self._metadata(connection).items())), before)
            if before != self._stamps():
                raise BackendConfigurationError("Source changed while opening; reopen the backend")
            with self._lock:
                if self._expected is None:
                    self._expected = identity
                elif identity != self._expected:
                    raise BackendConfigurationError("Source generation changed; reopen the backend")
            yield connection
            if before != self._stamps():
                raise BackendConfigurationError("Source changed during lookup; reopen the backend")

    def fingerprint(self) -> str:
        with self.session():
            assert self._expected is not None
            return self._expected.fingerprint


def remote_fingerprint(namespace: str, endpoint: str, **settings: Any) -> str:
    """Hash an effective endpoint and semantic settings without emitting credentials.

    This identifies configuration, not the changing contents of an unversioned
    remote service. Callers must supply an honest release/snapshot descriptor.
    """
    payload = json.dumps(
        {"endpoint": endpoint.rstrip("/"), "settings": settings},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return namespace + "-" + hashlib.sha256(payload.encode()).hexdigest()
