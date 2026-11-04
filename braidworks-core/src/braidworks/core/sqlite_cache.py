"""Opt-in SQLite implementation of the existing StrandCache port (local host only)."""

import logging
import math
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from .cache import StrandCacheKey
from .cache_codec import CODEC_VERSION, canonical_json, decode_json
from .cache_policy import CachePolicy
from .result import WeaveResult, WeaveStatus
from .sqlite import connection_scope, transaction

logger = logging.getLogger(__name__)
SCHEMA_VERSION = 1


class SQLiteStrandCache:
    """Short owned transactions, expiry, deterministic coverage and payload retention.

    No persistent connection is retained; close() is a compatibility no-op. ERROR
    entries are never admitted. Budget covers UTF-8 result payload bytes, not pages,
    WAL, index/key overhead or disk size. Rebuild incompatible caches explicitly.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        policy: CachePolicy | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = Path(path)
        self.policy = policy if policy is not None else CachePolicy()
        self._clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connection_scope(self.path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            with transaction(connection):
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS strand_cache_meta "
                    "(id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER, codec_version INTEGER)"
                )
                row = connection.execute(
                    "SELECT schema_version, codec_version FROM strand_cache_meta WHERE id=1"
                ).fetchone()
                if row is not None and tuple(row) != (SCHEMA_VERSION, CODEC_VERSION):
                    raise ValueError(
                        "Unsupported cache schema/codec; choose a new cache path or rebuild"
                    )
                if row is None:
                    if connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE name='strand_cache_entries'"
                    ).fetchone():
                        raise ValueError("Cache metadata missing; rebuild explicitly")
                    connection.execute(
                        "INSERT INTO strand_cache_meta VALUES (1, ?, ?)",
                        (SCHEMA_VERSION, CODEC_VERSION),
                    )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS strand_cache_entries ("
                    "sequence INTEGER PRIMARY KEY AUTOINCREMENT, base_key TEXT NOT NULL, "
                    "groups_json TEXT NOT NULL, payload TEXT NOT NULL, payload_bytes INTEGER NOT NULL, "
                    "created_at REAL NOT NULL, expires_at REAL NOT NULL, UNIQUE(base_key, groups_json))"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS strand_cache_base_key ON strand_cache_entries(base_key)"
                )

    def _now(self) -> float:
        now = self._clock()
        if not math.isfinite(now):
            raise ValueError("Cache clock must return finite seconds")
        return now

    @staticmethod
    def _key(key: StrandCacheKey) -> str:
        return canonical_json({"codec": CODEC_VERSION, "key": asdict(key)})

    def get(self, key: StrandCacheKey, requested_groups: frozenset[str]) -> WeaveResult | None:
        now = self._now()
        with connection_scope(self.path, readonly=True) as connection:
            metadata = connection.execute(
                "SELECT schema_version, codec_version FROM strand_cache_meta WHERE id=1"
            ).fetchone()
            if metadata is None or tuple(metadata) != (SCHEMA_VERSION, CODEC_VERSION):
                raise ValueError("Cache schema/codec changed; reopen or rebuild explicitly")
            rows = connection.execute(
                "SELECT groups_json, payload FROM strand_cache_entries "
                "WHERE base_key=? AND expires_at>?",
                (self._key(key), now),
            ).fetchall()
        candidates = []
        for row in rows:
            try:
                groups = decode_json(row["groups_json"])
                if not isinstance(groups, list) or any(type(item) is not str for item in groups):
                    raise ValueError("invalid group coverage")
                decoded = decode_json(row["payload"])
                if not isinstance(decoded, dict):
                    raise TypeError("cached result must be an object")
                for records in [
                    decoded.get("strands", []),
                    *[candidate.get("strands", []) for candidate in decoded.get("candidates", [])],
                ]:
                    if not isinstance(records, list):
                        raise TypeError("cached strands must be a list")
                    for strand in records:
                        confidence = strand.get("confidence", 1.0)
                        if (
                            not isinstance(strand.get("type_id"), str)
                            or type(confidence) not in (int, float)
                            or not 0 <= confidence <= 1
                        ):
                            raise ValueError("invalid cached strand identity/confidence")
                result = WeaveResult.from_json(decoded)
                if (
                    result.computed_groups != frozenset(groups)
                    or result.status is WeaveStatus.ERROR
                ):
                    raise ValueError("invalid cached result coverage/status")
                if (
                    result.capability_id != key.capability_id
                    or result.weaver_version != key.weaver_version
                    or result.backend_used != key.backend
                ):
                    raise ValueError("cached result identity mismatch")
                if result.computed_groups >= requested_groups:
                    candidates.append(result)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                logger.warning("Ignoring corrupt cache entry in %s: %s", self.path, exc)
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda result: (len(result.computed_groups), tuple(sorted(result.computed_groups))),
        )

    def put(self, key: StrandCacheKey, result: WeaveResult) -> None:
        ttl = self.policy.ttl(result.status)
        if ttl == 0 or self.policy.max_payload_bytes == 0:
            return
        if (
            result.capability_id != key.capability_id
            or result.weaver_version != key.weaver_version
            or result.backend_used != key.backend
        ):
            raise ValueError("Result identity does not match its cache key")
        payload = canonical_json(result.to_json())
        size = len(payload.encode("utf-8"))
        now = self._now()
        if not math.isfinite(now + ttl):
            raise ValueError("Cache expiry must be finite")
        groups = canonical_json(sorted(result.computed_groups))
        base_key = self._key(key)
        with connection_scope(self.path) as connection, transaction(connection):
            metadata = connection.execute(
                "SELECT schema_version, codec_version FROM strand_cache_meta WHERE id=1"
            ).fetchone()
            if metadata is None or tuple(metadata) != (SCHEMA_VERSION, CODEC_VERSION):
                raise ValueError("Cache schema/codec changed; reopen or rebuild explicitly")
            connection.execute("DELETE FROM strand_cache_entries WHERE expires_at<=?", (now,))
            connection.execute(
                "DELETE FROM strand_cache_entries WHERE base_key=? AND groups_json=?",
                (base_key, groups),
            )
            if size <= self.policy.max_payload_bytes:
                connection.execute(
                    "INSERT INTO strand_cache_entries (base_key, groups_json, payload, payload_bytes, created_at, expires_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (base_key, groups, payload, size, now, now + ttl),
                )
            total = connection.execute(
                "SELECT COALESCE(SUM(payload_bytes),0) FROM strand_cache_entries"
            ).fetchone()[0]
            for row in connection.execute(
                "SELECT sequence, payload_bytes FROM strand_cache_entries ORDER BY created_at, sequence"
            ).fetchall():
                if total <= self.policy.max_payload_bytes:
                    break
                connection.execute(
                    "DELETE FROM strand_cache_entries WHERE sequence=?", (row["sequence"],)
                )
                total -= row["payload_bytes"]

    def close(self) -> None:
        """All method-scoped connections are already closed."""
