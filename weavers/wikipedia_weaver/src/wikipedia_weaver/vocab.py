"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import (
    Capability,
    OutputGroup,
    Provenance,
    WeaverManifest,
)

WEAVER_ID = "wikipedia"
WEAVER_VERSION = "0.1.0"
WEAVER_TITLE = "Wikipedia pageviews (enwiki article title -> recent pageview count)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://wikimedia.org/api/rest_v1/",
    license="CC0-1.0",
    citation="Wikimedia REST API — pageviews. https://wikimedia.org/api/rest_v1/",
    attribution="Wikimedia Foundation",
)


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends.

    ``describe_pageviews`` is served by either backend — the live REST api or the
    dump-built local SQLite — so it's declared for whichever are wired.
    """
    served = tuple(b for b in ("api", "local") if b in backends)
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        capabilities=(
            Capability(
                id="describe_pageviews",
                consumes=frozenset({"wikipedia.title"}),
                produces=frozenset({"wikipedia.pageviews"}),
                output_groups=(OutputGroup(id="core", outputs=frozenset({"wikipedia.pageviews"})),),
                backends=served,
            ),
        ),
    )
