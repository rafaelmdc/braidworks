"""IdmappingWeaver — the UniProt ID-mapping hub weaver.

The routing/batching/mapping runtime is shared: this subclasses core's
``BackendDispatchWeaver`` and only declares its MANIFEST (from the edge table) and the
shared ``map_lookup`` mapper. The novel work — the async, batched ID-mapping flow — is in
the backend.
"""

from __future__ import annotations

from braidworks.core import BackendBase, BackendDispatchWeaver, WeaverManifest, map_lookup

from idmapping_weaver import vocab


class IdmappingWeaver(BackendDispatchWeaver):
    """Resolves every ID-mapping edge via the wired-in backends. The manifest declares them."""

    MAPPER = staticmethod(map_lookup)

    def __init__(self, backends: dict[str, BackendBase]) -> None:
        super().__init__(backends)  # raises if empty
        self.MANIFEST: WeaverManifest = vocab.build_manifest(backends=tuple(sorted(backends)))
