"""Live end-to-end tests for idmapping_weaver against the real UniProt ID-mapping API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run after
changes to the engine, to confirm the live async submit/poll/fetch flow and JSON shape
still match what the offline tests assume.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus, skip_if_transient

from idmapping_weaver import build_idmapping_weaver

RUN_LIVE = os.environ.get("BRAIDWORKS_RUN_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}
pytestmark = pytest.mark.skipif(
    not RUN_LIVE, reason="live E2E disabled; set BRAIDWORKS_RUN_LIVE=1 (real network calls)"
)


async def _accessions(capability, consume_type, value):
    weaver = build_idmapping_weaver()
    ss = StrandSet.from_strands("e1", [Strand(consume_type, value)])
    result = (
        await weaver.execute_batch(
            capability,
            [ss],
            requested_outputs=frozenset({"protein.uniprot.accession"}),
            backend="api",
        )
    )[0]
    skip_if_transient(result)
    return result


async def test_live_geneid_bridges_to_canonical_accession():
    """GeneID 7157 (human TP53) -> P04637, reviewed accession leading the set."""
    result = await _accessions("map_geneid", "gene.ncbi.id", "7157")
    assert result.status is WeaveStatus.OK
    accs = {s.type_id: s.value for s in result.strands}["protein.uniprot.accession"]
    assert isinstance(accs, list) and accs[0] == "P04637"


async def test_live_ensembl_gene_maps_to_accession():
    """Ensembl gene ENSG00000141510 (TP53) -> includes the canonical P04637."""
    result = await _accessions("map_ensembl", "gene.ensembl.id", "ENSG00000141510")
    assert result.status is WeaveStatus.OK
    accs = {s.type_id: s.value for s in result.strands}["protein.uniprot.accession"]
    assert "P04637" in accs


async def test_live_unknown_id_is_no_match():
    result = await _accessions("map_geneid", "gene.ncbi.id", "999999999")
    assert result.status is WeaveStatus.NO_MATCH
