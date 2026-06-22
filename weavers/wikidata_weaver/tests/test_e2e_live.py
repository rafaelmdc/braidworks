"""Live end-to-end test for wikidata_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from wikidata_weaver import build_wikidata_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def test_live_known_example():
    weaver = build_wikidata_weaver()
    # Ursus arctos (brown bear) -> Wikidata Q36341, enwiki "Brown_bear".
    ss = StrandSet.from_strands("e1", [Strand("organism.scientific_name", "Ursus arctos")])
    result = (
        await weaver.execute_batch(
            "resolve_taxon",
            [ss],
            requested_outputs=frozenset({"wikidata.qid", "wikipedia.title"}),
            backend="api",
        )
    )[0]
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced["wikidata.qid"] == "Q36341"
    assert produced["wikipedia.title"] == "Brown_bear"
