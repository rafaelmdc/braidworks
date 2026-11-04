"""WikidataWeaver — the concrete Braidworks weaver for Wikidata taxon names (scientific name -> QID, vernacular names, enwiki title).

The routing/batching/mapping runtime is shared: this subclasses core's
``BackendDispatchWeaver`` and only declares its MANIFEST (from the generated vocab)
and which shared mapper to use (``map_resolver``). The novel work is in the backends.
"""

from __future__ import annotations

from braidworks.core import (
    BackendBase,
    BackendDispatchWeaver,
    LookupRecord,
    WeaverManifest,
    map_lookup,
    map_resolver,
)

from wikidata_weaver import vocab


def _map_record(record, **kwargs):
    return (
        map_lookup(record, **kwargs)
        if isinstance(record, LookupRecord)
        else map_resolver(record, **kwargs)
    )


class WikidataWeaver(BackendDispatchWeaver):
    """Resolves inputs via the wired-in backends. The manifest declares only those."""

    MAPPER = staticmethod(_map_record)

    def __init__(self, backends: dict[str, BackendBase]) -> None:
        super().__init__(backends)  # raises if empty
        self.MANIFEST: WeaverManifest = vocab.build_manifest(backends=tuple(sorted(backends)))
