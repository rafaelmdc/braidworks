"""WikipediaWeaver — the concrete Braidworks weaver for Wikipedia pageviews (enwiki article title -> recent pageview count).

The routing/batching/mapping runtime is shared: this subclasses core's
``BackendDispatchWeaver`` and only declares its MANIFEST (from the generated vocab)
and which shared mapper to use (``map_lookup``). The novel work is in the backends.
"""

from __future__ import annotations

from braidworks.core import BackendBase, BackendDispatchWeaver, WeaverManifest, map_lookup

from wikipedia_weaver import vocab


class WikipediaWeaver(BackendDispatchWeaver):
    """Resolves inputs via the wired-in backends. The manifest declares only those."""

    MAPPER = staticmethod(map_lookup)

    def __init__(self, backends: dict[str, BackendBase]) -> None:
        super().__init__(backends)  # raises if empty
        self.MANIFEST: WeaverManifest = vocab.build_manifest(backends=tuple(sorted(backends)))
