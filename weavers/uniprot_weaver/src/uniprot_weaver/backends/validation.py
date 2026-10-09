"""Shared source-local response shape checks; no transport or domain selection."""

from typing import Any


class _InvalidResponse(ValueError):
    """An invalid UniProt search or mapping-job source response."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _InvalidResponse(f"UniProt {label} must be an object")
    return value


def _rows(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise _InvalidResponse(f"UniProt {label} must be an object list")
    return value
