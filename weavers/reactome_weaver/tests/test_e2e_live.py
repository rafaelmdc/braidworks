"""Live end-to-end test for reactome_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from reactome_weaver import build_reactome_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def _pathways(weaver, accession):
    ss = StrandSet.from_strands("e1", [Strand("protein.uniprot.accession", accession)])
    return (
        await weaver.execute_batch(
            "resolve_pathways",
            [ss],
            requested_outputs=frozenset(
                {
                    "pathway.reactome.id",
                    "pathway.reactome.names",
                    "pathway.reactome.count",
                    "pathway.reactome.records",
                }
            ),
            backend="api",
        )
    )[0]


async def test_live_tp53_pathways():
    """Drift detector: P04637 (human TP53) participates in many Reactome pathways.

    Structural truth: distinct pathways come back deduped, count matches records, every
    record carries an R- stable id, and they're ordered by stable id (deterministic).
    """
    weaver = build_reactome_weaver()
    result = await _pathways(weaver, "P04637")
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    records = produced["pathway.reactome.records"]
    assert produced["pathway.reactome.count"] >= len(records) > 0
    assert all(r["st_id"].startswith("R-") for r in records)
    assert [r["st_id"] for r in records] == sorted(r["st_id"] for r in records)
    # The fan dimension: the full distinct stId set, deduped + ordered, matching count.
    ids = produced["pathway.reactome.id"]
    assert isinstance(ids, list) and len(ids) == produced["pathway.reactome.count"]
    assert ids == sorted(set(ids)) and all(i.startswith("R-") for i in ids)


async def test_live_malformed_accession_is_no_match():
    weaver = build_reactome_weaver()
    result = await _pathways(weaver, "NOTAREALACC")
    assert result.status is WeaveStatus.NO_MATCH
