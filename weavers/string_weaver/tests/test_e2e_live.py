"""Live end-to-end test for string_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus, skip_if_transient

from string_weaver import build_string_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def _interactions(weaver, accession):
    ss = StrandSet.from_strands("e1", [Strand("protein.uniprot.accession", accession)])
    return (
        await weaver.execute_batch(
            "list_interactions",
            [ss],
            requested_outputs=frozenset(
                {"protein.query", "protein.interaction.partners", "protein.interaction.count",
                 "protein.interaction.records"}
            ),
            backend="api",
        )
    )[0]


async def test_live_tp53_has_interaction_partners():
    """Drift detector: P04637 (human TP53) returns scored interaction partners.

    Structural truth (not a fixed partner list): some partners come back, the count
    matches, scores are in [0,1], and MDM2 — TP53's canonical regulator — is among
    them. Confirms the live STRING JSON still maps to our leaves.
    """
    weaver = build_string_weaver()
    result = await _interactions(weaver, "P04637")
    skip_if_transient(result)
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    partners = produced["protein.interaction.partners"]
    records = produced["protein.interaction.records"]
    assert produced["protein.interaction.count"] == len(partners) == len(records)
    assert all(0.0 <= r["score"] <= 1.0 for r in records)
    assert "MDM2" in partners
    # the fan dimension: distinct partner names as protein.query (chains into uniprot)
    queries = produced["protein.query"]
    assert "MDM2" in queries and len(queries) == len(set(queries))


async def test_live_unknown_accession_is_no_match():
    weaver = build_string_weaver()
    result = await _interactions(weaver, "X0X0X0")
    skip_if_transient(result)
    assert result.status is WeaveStatus.NO_MATCH
