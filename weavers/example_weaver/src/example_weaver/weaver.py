"""ExampleWeaver — the concrete Braidworks weaver for the example traits source.

The routing/batching/mapping runtime is shared from core: this subclasses
``BackendDispatchWeaver`` and only declares its MANIFEST (from the generated vocab)
and the shared mapper (``map_lookup``). The real work is in the local backend.
"""

from __future__ import annotations

from braidworks.core import BackendBase, BackendDispatchWeaver, WeaverManifest, map_lookup

from example_weaver import vocab


class ExampleWeaver(BackendDispatchWeaver):
    """Resolves inputs via the wired-in backends. The manifest declares only those."""

    MAPPER = staticmethod(map_lookup)

    def __init__(self, backends: dict[str, BackendBase]) -> None:
        super().__init__(backends)  # raises if empty
        self.MANIFEST: WeaverManifest = vocab.build_manifest(backends=tuple(sorted(backends)))
