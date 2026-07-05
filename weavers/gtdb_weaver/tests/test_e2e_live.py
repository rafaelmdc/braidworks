"""Live end-to-end test for gtdb_weaver against the real local API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from gtdb_weaver import build_gtdb_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def test_live_known_example():
    # The live api backend resolves a GTDB species name over the network.
    weaver = build_gtdb_weaver(enable_api=True)
    ss = StrandSet.from_strands("e1", [Strand("organism.scientific_name", "Escherichia coli")])
    result = (
        await weaver.execute_batch(
            "describe_gtdb_taxonomy",
            [ss],
            requested_outputs=frozenset({"gtdb.taxon.id", "gtdb.lineage"}),
            backend="api",
        )
    )[0]
    assert result.status is WeaveStatus.OK
    strands = {s.type_id: s.value for s in result.strands}
    assert strands["gtdb.taxon.id"] == "s__Escherichia coli"
    lineage = strands["gtdb.lineage"]
    assert {"rank": "domain", "name": "Bacteria"} in lineage
    assert {"rank": "species", "name": "Escherichia coli"} in lineage
