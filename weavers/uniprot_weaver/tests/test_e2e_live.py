"""Live end-to-end test for uniprot_weaver against the real api API.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run it
after changes that touch the api backend's request/parse code, to confirm the live
schema still matches what the offline tests assume. Replace the TODO input/asserts
with a known-truth example from the real source.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus, skip_if_transient

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
    skip_if_transient(result)
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
    skip_if_transient(result)
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
    skip_if_transient(result)
    assert result.status is WeaveStatus.NO_MATCH


async def _idmap(capability, input_type, value, output):
    weaver = build_uniprot_weaver()
    ss = StrandSet.from_strands("g1", [Strand(input_type, value)])
    result = (
        await weaver.execute_batch(
            capability, [ss], requested_outputs=frozenset({output}), backend="api"
        )
    )[0]
    skip_if_transient(result)
    return result


async def test_live_map_to_accession_from_geneid():
    """Async ID-mapping: NCBI GeneID 7157 (human TP53) -> P04637 (reviewed leads)."""
    result = await _idmap("map_to_accession", "gene.ncbi.id", "7157", "protein.uniprot.accession")
    assert result.status is WeaveStatus.OK
    accs = {s.type_id: s.value for s in result.strands}["protein.uniprot.accession"]
    assert isinstance(accs, list) and accs[0] == "P04637"


async def test_live_map_to_accession_from_ensembl():
    """Alternative input: Ensembl gene ENSG00000141510 (TP53) -> includes P04637."""
    result = await _idmap(
        "map_to_accession", "gene.ensembl.id", "ENSG00000141510", "protein.uniprot.accession"
    )
    assert result.status is WeaveStatus.OK
    accs = {s.type_id: s.value for s in result.strands}["protein.uniprot.accession"]
    assert "P04637" in accs


async def test_live_map_from_accession_to_geneid():
    """Reverse bridge: accession P04637 -> NCBI GeneID 7157 (routes by requested output)."""
    result = await _idmap("map_from_accession", "protein.uniprot.accession", "P04637", "gene.ncbi.id")
    assert result.status is WeaveStatus.OK
    gene_ids = {s.type_id: s.value for s in result.strands}["gene.ncbi.id"]
    assert any(str(g) == "7157" for g in gene_ids)


async def test_live_map_to_accession_unknown_is_no_match():
    result = await _idmap("map_to_accession", "gene.ncbi.id", "999999999", "protein.uniprot.accession")
    assert result.status is WeaveStatus.NO_MATCH
