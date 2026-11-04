"""Explicit local persistence configuration shared by human interface adapters."""

from dataclasses import dataclass, field
from typing import Any

from .cache_policy import CachePolicy
from .persistent_query import _validate_lease, start_run
from .query import execute_query
from .run_store import SQLiteRunStore
from .sqlite_cache import SQLiteStrandCache


@dataclass(frozen=True)
class QueryPersistence:
    cache_db: str | None = None
    run_db: str | None = None
    run_id: str | None = None
    cache_policy: CachePolicy = field(default_factory=CachePolicy)
    lease_seconds: float = 60

    def __post_init__(self):
        for name in ("cache_db", "run_db", "run_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a nonempty string or None")
        if self.run_id is not None and self.run_db is None:
            raise ValueError("run_id requires run_db")
        if not isinstance(self.cache_policy, CachePolicy):
            raise TypeError("cache_policy must be CachePolicy")
        _validate_lease(self.lease_seconds)

    def to_json(self) -> dict[str, Any]:
        return {
            "version": 1,
            "cache_db": self.cache_db,
            "run_db": self.run_db,
            "run_id": self.run_id,
            "cache_policy": self.cache_policy.to_json(),
            "lease_seconds": self.lease_seconds,
        }

    @classmethod
    def from_json(cls, data):
        if not isinstance(data, dict):
            raise TypeError("Query persistence configuration must be an object")
        if set(data) - {"version", "cache_db", "run_db", "run_id", "cache_policy", "lease_seconds"}:
            raise ValueError("Unknown query persistence configuration fields")
        if data.get("version") != 1:
            raise ValueError("Unsupported query persistence configuration version")
        return cls(
            data.get("cache_db"),
            data.get("run_db"),
            data.get("run_id"),
            CachePolicy.from_json(data.get("cache_policy", {})),
            data.get("lease_seconds", 60),
        )

    def cache(self):
        return SQLiteStrandCache(self.cache_db, policy=self.cache_policy) if self.cache_db else None

    def store(self, *, create=True):
        if self.run_db is None:
            raise ValueError("A saved runs path is required")
        return SQLiteRunStore(self.run_db, create=create)


async def execute_managed_query(
    registry, prepared, persistence: QueryPersistence | None = None, *, on_event=None, on_saved=None
):
    """Execute through the same service with optional local cache/run adapters."""
    persistence = persistence if persistence is not None else QueryPersistence()
    cache = persistence.cache()
    if persistence.run_db is None:
        return await execute_query(registry, prepared, cache=cache, on_event=on_event)
    checkpoint = await start_run(
        registry,
        prepared,
        persistence.store(),
        run_id=persistence.run_id,
        cache=cache,
        on_event=on_event,
        on_saved=on_saved,
        lease_seconds=persistence.lease_seconds,
    )
    return checkpoint.state.result
