"""Live end-to-end tests for gtdb_weaver against real GTDB sources.

Opt-in: set ``BRAIDWORKS_RUN_LIVE=1`` to enable (makes real network calls). Run after
changes that touch a backend's request/parse code, to confirm the live schema still
matches what the offline tests assume. The tree-placement test additionally downloads the
GTDB crosswalk + reference trees (~160 MB) on first run, into ``BRAIDWORKS_DATA_DIR``.

Verified against GTDB R232.
"""

from __future__ import annotations

import os

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from gtdb_weaver import build_gtdb_weaver, cophenetic

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


async def _placements(taxids: list[str]) -> dict[str, list]:
    """Real tree placements for taxids via the local backend (downloads GTDB data if absent)."""
    weaver = build_gtdb_weaver(auto_setup=True, enable_tree_placement=True)
    strand_sets = [StrandSet.from_strands(t, [Strand("ncbi.taxon.id", t)]) for t in taxids]
    results = await weaver.execute_batch(
        "describe_gtdb_tree_placement",
        strand_sets,
        requested_outputs=frozenset({"gtdb.tree.rootpath"}),
        backend="local",
    )
    out: dict[str, list] = {}
    for taxid, result in zip(taxids, results):
        if result.status is WeaveStatus.OK:
            out[taxid] = {s.type_id: s.value for s in result.strands}["gtdb.tree.rootpath"]
    return out


async def test_live_tree_placement_distances_are_sane():
    """taxid -> reference-tree placement, and patristic distance tracks real phylogeny.

    Confirms the two real-data assumptions the fixture can't: the reference-tree URLs and that
    the metadata `accession` equals the tree leaf label (so the crosswalk join lands). Known
    taxa: E. coli (562) & Salmonella enterica (28901) are both Enterobacteriaceae (close);
    Bacteroides fragilis (817) is a different phylum (far).
    """
    paths = await _placements(["562", "28901", "817"])
    assert set(paths) == {"562", "28901", "817"}, "an organism failed to place on the tree"
    close = cophenetic(paths["562"], paths["28901"])
    far = cophenetic(paths["562"], paths["817"])
    assert 0.0 < close < far
