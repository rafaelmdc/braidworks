"""Opt-in live E2E: hit the real GMrepo API and resolve a known taxid.

Self-skips unless BRAIDWORKS_RUN_LIVE=1. Rather than build the full local DB (a
~3000-call, ~10-20 min crawl), it does a targeted mini-build — the global overview
plus one taxon's abundance rows — so the real API shapes (trailing-slash POST, the
taxon-centric endpoint, field names) are exercised cheaply. Run after touching
setup.py or when GMrepo changes its API:

    BRAIDWORKS_RUN_LIVE=1 make -C weavers/gmrepo_weaver test-live
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus, skip_if_transient

from gmrepo_weaver.backends.local import GmrepoLocalBackend
from gmrepo_weaver.setup import _overview_rows, _post, _taxon_associations, write_db
from gmrepo_weaver.weaver import GmrepoWeaver

pytestmark = pytest.mark.skipif(
    not os.environ.get("BRAIDWORKS_RUN_LIVE"),
    reason="live E2E; set BRAIDWORKS_RUN_LIVE=1 (hits the GMrepo API)",
)

_BACTEROIDES = 816  # a genus present in every gut-metagenome phenotype set


async def test_live_minibuild_and_resolve(tmp_path: Path):
    overview = _overview_rows(_post("get_all_gut_microbes", {}))
    assert len(overview) > 100, "expected a large gut-microbe universe"
    assert any(r["ncbi_taxon_id"] == _BACTEROIDES for r in overview)

    picked = [r for r in overview if r["ncbi_taxon_id"] == _BACTEROIDES]
    payload = _post(
        "getPhenotypesAndAbundanceSummaryOfAAssociatedTaxon",
        {"ncbi_taxon_id": _BACTEROIDES},
    )
    associations = _taxon_associations(_BACTEROIDES, payload)
    assert associations, "Bacteroides should carry phenotype-abundance rows"

    db = tmp_path / "gmrepo.sqlite"
    write_db(db, overview=picked, associations=associations, phenotypes=[])
    weaver = GmrepoWeaver({"local": GmrepoLocalBackend(db)})

    out = await weaver.execute_batch(
        "gmrepo.list_abundances",
        [StrandSet.from_strands("e", [Strand("ncbi.taxon.id", _BACTEROIDES)])],
        requested_outputs=frozenset(
            {
                "microbe.abundance.overview",
                "microbe.abundance.count",
                "microbe.abundance.associations",
            }
        ),
        backend="local",
    )
    r = out[0]
    skip_if_transient(r)
    assert r.status is WeaveStatus.OK
    sm = {s.type_id: s.value for s in r.strands}
    assert sm["microbe.abundance.count"] >= 1
    assert sm["microbe.abundance.overview"]["name"].lower().startswith("bacteroides")
    # abundance rows carry real relative-abundance numbers
    assert any(
        row.get("abundance_median") is not None for row in sm["microbe.abundance.associations"]
    )

    # a taxid GMrepo does not track resolves to NO_MATCH, not an error
    miss = await weaver.execute_batch(
        "gmrepo.list_abundances",
        [StrandSet.from_strands("e", [Strand("ncbi.taxon.id", 999999999)])],
        requested_outputs=frozenset({"microbe.abundance.count"}),
        backend="local",
    )
    skip_if_transient(miss[0])
    assert miss[0].status is WeaveStatus.NO_MATCH
