"""Live end-to-end test against the real BacDive v2 API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (it makes real network calls to
api.bacdive.dsmz.de — no key required). It resolves a few well-characterized
species through the weaver and asserts the type strain's core traits, confirming
the JSON paths the offline tests assume still match the live record schema. Run
this after any change that touches the api backend's parsing.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from bacdive_weaver import build_bacdive_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason="live BacDive E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)",
)


async def _resolve(weaver, name: str):
    ss = StrandSet.from_strands("e1", [Strand("organism.scientific_name", name)])
    results = await weaver.execute_batch(
        "describe_traits",
        [ss],
        requested_outputs=frozenset({"microbe.trait.gram_stain", "microbe.trait.cell_shape"}),
        backend="api",
    )
    return results[0]


async def test_live_ecoli_type_strain_traits():
    weaver = build_bacdive_weaver(max_strains_scanned=2000)
    result = await _resolve(weaver, "Escherichia coli")
    assert result.status is WeaveStatus.OK
    values = {s.type_id: s.value for s in result.strands}
    assert values.get("microbe.trait.gram_stain") == "negative"
    assert "rod" in values.get("microbe.trait.cell_shape", "").lower()


async def test_live_unknown_name_is_no_match():
    weaver = build_bacdive_weaver()
    result = await _resolve(weaver, "Notarealus fakenamei")
    assert result.status is WeaveStatus.NO_MATCH
