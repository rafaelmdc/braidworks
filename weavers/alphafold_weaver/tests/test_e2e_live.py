"""Live end-to-end test for alphafold_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus, skip_if_transient

from alphafold_weaver import build_alphafold_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def _model(weaver, accession):
    ss = StrandSet.from_strands("e1", [Strand("protein.uniprot.accession", accession)])
    return (
        await weaver.execute_batch(
            "describe_model",
            [ss],
            requested_outputs=frozenset(
                {"structure.alphafold.entry_id", "structure.alphafold.mean_plddt",
                 "structure.alphafold.model_url"}
            ),
            backend="api",
        )
    )[0]


async def test_live_tp53_canonical_model():
    """Known truth: P04637 -> the canonical AlphaFold model AF-P04637-F1.

    The canonical entry id is exactly stable; mean pLDDT is a 0-100 confidence and the
    model URL points at a real file. Confirms the live JSON still maps to our leaves.
    """
    weaver = build_alphafold_weaver()
    result = await _model(weaver, "P04637")
    skip_if_transient(result)
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced["structure.alphafold.entry_id"] == "AF-P04637-F1"
    assert 0.0 <= produced["structure.alphafold.mean_plddt"] <= 100.0
    assert produced["structure.alphafold.model_url"].endswith(".pdb")


async def test_live_malformed_accession_is_no_match():
    # AlphaFold has near-universal coverage, so a real-but-unmodeled accession is rare;
    # a malformed identifier (400) is the reliable NO_MATCH case.
    weaver = build_alphafold_weaver()
    result = await _model(weaver, "NOTAREALACC")
    skip_if_transient(result)
    assert result.status is WeaveStatus.NO_MATCH
