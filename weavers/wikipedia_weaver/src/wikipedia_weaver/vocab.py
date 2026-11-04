"""Capabilities and manifest for the weaver — generated from weaver.spec.toml.

The manifest is the machine-readable mirror of the spec; keep them in sync
(``weaverkit verify`` checks this). Edit the spec and regenerate rather than
hand-editing capabilities here.
"""

from __future__ import annotations

from braidworks.core import (
    Capability,
    OutputGroup,
    Parameter,
    Provenance,
    WeaverManifest,
)

WEAVER_ID = "wikipedia"
WEAVER_VERSION = "0.1.9"
WEAVER_TITLE = "Wikipedia pageviews (enwiki article title -> recent pageview count)"

# Source/license/citation for automatic references — mirrors weaver.spec.toml.
PROVENANCE = Provenance(
    source_url="https://wikimedia.org/api/rest_v1/",
    license="CC0-1.0",
    citation="Wikimedia REST API — pageviews. https://wikimedia.org/api/rest_v1/",
    attribution="Wikimedia Foundation",
)

# What each consumed/produced type means — from the spec's [types] table, else
# weaverkit's key registry. Lets users find fields by meaning.
TYPE_DESCRIPTIONS = {
    "wikipedia.pageviews": "English-Wikipedia pageview subtotal; compare only matching measurement scopes.",
    "wikipedia.pageviews.measurement": "Pageview period, project, access, agent and observed/requested monthly-bin coverage.",
    "wikipedia.pageviews.series": "Ordered observed monthly bins; absent months are not measured zero.",
    "wikipedia.pageviews.title": "Supplied English Wikipedia article key and explicit redirect policy.",
    "wikipedia.title": "English Wikipedia article title for one taxon — the pageviews join key.",
}


def build_manifest(*, backends: tuple[str, ...]) -> WeaverManifest:
    """Declare every capability for the wired-in backends."""
    return WeaverManifest(
        weaver_id=WEAVER_ID,
        version=WEAVER_VERSION,
        title=WEAVER_TITLE,
        provenance=PROVENANCE,
        type_descriptions=dict(TYPE_DESCRIPTIONS),
        capabilities=(
            Capability(
                id="describe_pageviews",
                consumes=frozenset({"wikipedia.title"}),
                produces=frozenset(
                    {
                        "wikipedia.pageviews",
                        "wikipedia.pageviews.measurement",
                        "wikipedia.pageviews.series",
                        "wikipedia.pageviews.title",
                    }
                ),
                output_groups=(
                    OutputGroup(
                        id="core",
                        outputs=frozenset(
                            {"wikipedia.pageviews", "wikipedia.pageviews.measurement"}
                        ),
                    ),
                    OutputGroup(
                        id="series",
                        outputs=frozenset(
                            {"wikipedia.pageviews.series", "wikipedia.pageviews.title"}
                        ),
                    ),
                ),
                backends=tuple(
                    b
                    for b in (
                        "api",
                        "local",
                    )
                    if b in backends
                ),
                parameters=(
                    Parameter(
                        name="months",
                        type="int",
                        enum=(),
                        default=None,
                        description="Completed monthly bins (API default 12; local supports only 1)",
                    ),
                    Parameter(
                        name="end_month",
                        type="string",
                        enum=(),
                        default=None,
                        description="Final completed month YYYYMM (API default previous month; local dump month)",
                    ),
                    Parameter(
                        name="agent",
                        type="string",
                        enum=(
                            "all-agents",
                            "user",
                            "spider",
                            "automated",
                        ),
                        default=None,
                        description="Agent scope (API default all-agents; local supports only user)",
                    ),
                ),
            ),
        ),
    )
