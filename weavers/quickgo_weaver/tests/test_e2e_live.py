"""Live end-to-end test for quickgo_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from quickgo_weaver import build_quickgo_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def _go(weaver, accession):
    ss = StrandSet.from_strands("e1", [Strand("protein.uniprot.accession", accession)])
    return (
        await weaver.execute_batch(
            "list_go_terms",
            [ss],
            requested_outputs=frozenset(
                {"go.term", "go.molecular_function", "go.biological_process",
                 "go.cellular_component", "go.count", "go.records"}
            ),
            backend="api",
        )
    )[0]


async def test_live_tp53_go_annotations():
    """Drift detector: P04637 (human TP53) has GO terms across aspects.

    Structural truth: distinct terms come back deduped, count matches the records,
    every record carries a GO id + aspect, and apoptosis (a hallmark p53 process) is
    annotated. Confirms the live QuickGO JSON still maps to our leaves.
    """
    weaver = build_quickgo_weaver()
    result = await _go(weaver, "P04637")
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    records = produced["go.records"]
    assert produced["go.count"] == len(records) > 0
    assert all(r["go_id"].startswith("GO:") and r["aspect"] for r in records)
    assert [r["go_id"] for r in records] == sorted(r["go_id"] for r in records)  # deterministic
    # apoptotic process GO:0006915 is a canonical p53 annotation
    assert any(r["go_id"] == "GO:0006915" for r in records)
    # the fan dimension: the full distinct GO-id set, matching the records
    assert produced["go.term"] == [r["go_id"] for r in records]


async def test_live_unknown_accession_is_no_match():
    weaver = build_quickgo_weaver()
    result = await _go(weaver, "X0X0X0")
    assert result.status is WeaveStatus.NO_MATCH
