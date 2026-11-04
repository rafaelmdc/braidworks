"""Validate per-query parameter targeting before a route performs backend I/O."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from braidworks.core.capability import Capability


def map_parameter_items(
    items: list[tuple[str | None, str, Any]], capabilities: dict[str, Capability]
) -> dict[str, dict[str, Any]]:
    """Map bare names to declaring steps and validate every explicit scope."""
    mapped: dict[str, dict[str, Any]] = {}
    for scope, name, value in items:
        if scope is not None:
            if scope not in capabilities:
                raise ValueError(f"parameter scope {scope!r} is not in this route")
            targets = [scope]
        else:
            targets = [
                cid
                for cid, cap in capabilities.items()
                if any(parameter.name == name for parameter in cap.parameters)
            ]
        if not targets:
            raise ValueError(f"no step in this route accepts a parameter named {name!r}")
        for cid in targets:
            mapped.setdefault(cid, {})[name] = value
    # Validate/coerce the whole request before executing any step. Executors also
    # resolve defaults for capabilities that have no caller-supplied parameters.
    return {cid: capabilities[cid].resolve_params(values) for cid, values in mapped.items()}


def validate_scoped_parameters(
    params: dict[str, dict[str, Any]], capabilities: dict[str, Capability]
) -> dict[str, dict[str, Any]]:
    unknown = set(params) - capabilities.keys()
    if unknown:
        raise ValueError(f"parameter scope(s) {sorted(unknown)} are not in this route")
    return {cid: capabilities[cid].resolve_params(values) for cid, values in params.items()}
