"""Live end-to-end test for pdbe_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus, skip_if_transient

from pdbe_weaver import build_pdbe_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def _structures(weaver, accession):
    ss = StrandSet.from_strands("e1", [Strand("protein.uniprot.accession", accession)])
    return (
        await weaver.execute_batch(
            "list_structures",
            [ss],
            requested_outputs=frozenset(
                {"pdb.id", "structure.pdb.ids", "structure.pdb.count", "structure.pdb.records"}
            ),
            backend="api",
        )
    )[0]


async def test_live_tp53_has_structures():
    """Drift detector: P04637 (human TP53) has many PDB structures, deduped + ordered.

    Structural truth: distinct PDB ids come back, count >= len(ids) (ids are the top N),
    every record carries a 4-char pdb_id, and they're ordered best-first by coverage.
    Confirms the live PDBe JSON still maps to our leaves.
    """
    weaver = build_pdbe_weaver()
    result = await _structures(weaver, "P04637")
    skip_if_transient(result)
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    ids, recs = produced["structure.pdb.ids"], produced["structure.pdb.records"]
    assert produced["structure.pdb.count"] >= len(ids) > 0
    assert all(len(r["pdb_id"]) == 4 for r in recs)
    covs = [r.get("coverage") or 0.0 for r in recs]
    assert covs == sorted(covs, reverse=True)  # best coverage first
    # the fan dimension: the full distinct id set, matching count
    fan = produced["pdb.id"]
    assert isinstance(fan, list) and len(fan) == produced["structure.pdb.count"]
    assert fan == sorted(set(fan), key=fan.index)  # deduped, order preserved


async def test_live_unknown_accession_is_no_match():
    weaver = build_pdbe_weaver()
    result = await _structures(weaver, "X0X0X0")
    skip_if_transient(result)
    assert result.status is WeaveStatus.NO_MATCH


async def _describe(weaver, pdb_id):
    ss = StrandSet.from_strands("e1", [Strand("pdb.id", pdb_id)])
    return (
        await weaver.execute_batch(
            "describe_structure",
            [ss],
            requested_outputs=frozenset(
                {"structure.pdb.title", "structure.pdb.method",
                 "structure.pdb.release_date", "structure.pdb.detail"}
            ),
            backend="api",
        )
    )[0]


async def test_live_describe_1tup():
    """Drift detector: 1tup (p53/DNA) summary still maps to our describe leaves."""
    weaver = build_pdbe_weaver()
    result = await _describe(weaver, "1tup")
    skip_if_transient(result)
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert "P53" in produced["structure.pdb.title"].upper()
    assert produced["structure.pdb.method"]  # an experimental method string
    assert produced["structure.pdb.detail"]["pdb_id"] == "1tup"


async def test_live_describe_unknown_is_no_match():
    weaver = build_pdbe_weaver()
    result = await _describe(weaver, "9zz9")
    skip_if_transient(result)
    assert result.status is WeaveStatus.NO_MATCH
