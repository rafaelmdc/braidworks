"""Live end-to-end test for uniprot_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from uniprot_weaver import build_uniprot_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def test_live_gene_symbol_resolves_with_bridge():
    """Drift detector: gene symbol 'TP53' -> a reviewed p53 protein + the taxid bridge.

    A bare gene symbol does not deterministically map to one species' protein (every
    species' TP53 is an equal exact match), so we assert *structural* truth — the live
    JSON still maps to our produced keys, including ``ncbi.taxon.id`` — not a specific
    accession. (The offline golden pins P04637 via the deterministic fixture.)
    """
    weaver = build_uniprot_weaver()
    ss = StrandSet.from_strands("e1", [Strand("protein.query", "TP53")])
    result = (
        await weaver.execute_batch(
            "resolve_protein",
            [ss],
            requested_outputs=frozenset(
                {"protein.uniprot.accession", "protein.gene", "protein.reviewed", "ncbi.taxon.id"}
            ),
            backend="api",
        )
    )[0]
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced.get("protein.gene", "").upper() == "TP53"
    assert produced.get("protein.reviewed") == "reviewed"
    assert produced.get("protein.uniprot.accession")  # some accession present
    taxid = produced.get("ncbi.taxon.id")  # the bridge key, canonicalized to int
    assert isinstance(taxid, int) and taxid > 0


async def test_live_accession_is_deterministic():
    """An accession query is exact and stable: 'P04637' -> human p53 (taxid 9606)."""
    weaver = build_uniprot_weaver()
    ss = StrandSet.from_strands("e1", [Strand("protein.query", "P04637")])
    result = (
        await weaver.execute_batch(
            "resolve_protein",
            [ss],
            requested_outputs=frozenset({"protein.uniprot.accession", "ncbi.taxon.id"}),
            backend="api",
        )
    )[0]
    assert result.status is WeaveStatus.OK
    produced = {s.type_id: s.value for s in result.strands}
    assert produced.get("protein.uniprot.accession") == "P04637"
    assert produced.get("ncbi.taxon.id") == 9606


async def test_live_unknown_query_is_no_match():
    weaver = build_uniprot_weaver()
    ss = StrandSet.from_strands("e1", [Strand("protein.query", "zzzznotarealprotein9999")])
    result = (
        await weaver.execute_batch(
            "resolve_protein",
            [ss],
            requested_outputs=frozenset({"protein.uniprot.accession"}),
            backend="api",
        )
    )[0]
    assert result.status is WeaveStatus.NO_MATCH
