"""Declaration-aware capability checks shared by direct interfaces and dispatch."""

from braidworks.core.capability import Capability
from braidworks.core.exceptions import BackendUnavailable, UnsupportedCapability
from braidworks.core.weaver import BaseWeaver


def require_capability(
    weaver: BaseWeaver, capability_id: str, backend: str | None = None
) -> Capability:
    """Check support and enabled backend compatibility without probing readiness."""
    active = weaver.MANIFEST.capability(capability_id)
    declared = weaver.declared_manifest().capability(capability_id)
    identity = f"{weaver.MANIFEST.weaver_id} / {capability_id}"
    if declared is None:
        raise UnsupportedCapability(f"{identity}: no capability with this identifier")
    if active is None:
        raise BackendUnavailable(
            f"{identity}: required backends {', '.join(declared.backends)} are not enabled; "
            "enable a supported backend and retry"
        )
    if backend is not None and backend not in active.backends:
        reason = "not enabled" if backend in declared.backends else "not supported"
        raise BackendUnavailable(
            f"{identity}: backend {backend!r} is {reason}; "
            f"enabled backends: {', '.join(active.backends)}"
        )
    return active
