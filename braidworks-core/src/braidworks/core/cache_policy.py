"""Admission/freshness policy for opt-in lookup persistence, separate from review."""

import math
from dataclasses import dataclass
from typing import Any

from .result import WeaveStatus


@dataclass(frozen=True)
class CachePolicy:
    positive_ttl: float = 3600.0
    negative_ttl: float = 300.0
    max_payload_bytes: int = 256 * 1024 * 1024

    def __post_init__(self):
        for value in (self.positive_ttl, self.negative_ttl):
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("Cache TTLs must be finite and nonnegative")
        if type(self.max_payload_bytes) is not int or self.max_payload_bytes < 0:
            raise ValueError("Cache payload budget must be a nonnegative integer")

    def ttl(self, status: WeaveStatus) -> float:
        if status is WeaveStatus.ERROR:
            return 0.0
        return self.negative_ttl if status is WeaveStatus.NO_MATCH else self.positive_ttl

    def to_json(self) -> dict[str, Any]:
        return {
            "positive_ttl": self.positive_ttl,
            "negative_ttl": self.negative_ttl,
            "max_payload_bytes": self.max_payload_bytes,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CachePolicy":
        return cls(**data)
