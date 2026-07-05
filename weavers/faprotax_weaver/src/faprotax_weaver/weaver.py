"""FaprotaxWeaver — the concrete Braidworks weaver for FAPROTAX ecological function (organism lineage -> functional groups).

The routing/batching/mapping runtime is shared: this subclasses core's
``BackendDispatchWeaver`` and only declares its MANIFEST (from the generated vocab)
and which shared mapper to use (``map_lookup``). The novel work is in the backends.
"""

from __future__ import annotations

from braidworks.core import BackendBase, BackendDispatchWeaver, WeaverManifest, map_lookup

from faprotax_weaver import vocab


class FaprotaxWeaver(BackendDispatchWeaver):
    """Resolves inputs via the wired-in backends. The manifest declares only those."""

    MAPPER = staticmethod(map_lookup)

    def __init__(self, backends: dict[str, BackendBase]) -> None:
        super().__init__(backends)  # raises if empty
        self.MANIFEST: WeaverManifest = vocab.build_manifest(backends=tuple(sorted(backends)))
