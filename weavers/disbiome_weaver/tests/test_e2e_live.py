"""Opt-in live E2E: build the real Disbiome DB from the API and resolve a known taxid.

Self-skips unless BRAIDWORKS_RUN_LIVE=1 (it fetches ~7 MB from the Disbiome API and
builds a local SQLite in a temp dir). Run after touching setup.py / the API shapes:

    BRAIDWORKS_RUN_LIVE=1 make -C weavers/disbiome_weaver test-live
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus

from disbiome_weaver.backends.local import DisbiomeLocalBackend
from disbiome_weaver.setup import ensure_disbiome_db
from disbiome_weaver.weaver import DisbiomeWeaver

pytestmark = pytest.mark.skipif(
    not os.environ.get("BRAIDWORKS_RUN_LIVE"),
    reason="live E2E; set BRAIDWORKS_RUN_LIVE=1 (fetches ~7 MB from the Disbiome API)",
)


async def test_live_build_and_resolve(tmp_path: Path):
    db = ensure_disbiome_db(tmp_path / "disbiome.sqlite", auto=True)
    weaver = DisbiomeWeaver({"local": DisbiomeLocalBackend(db)})

    # 1591 = Lactobacillus, present in Disbiome with disease associations.
    out = await weaver.execute_batch(
        "disbiome.list_diseases",
        [StrandSet.from_strands("e", [Strand("ncbi.taxon.id", 1591)])],
        requested_outputs=frozenset(
            {"microbe.disease.names", "microbe.disease.count", "microbe.disease.records"}
        ),
        backend="local",
    )
    r = out[0]
    assert r.status is WeaveStatus.OK
    sm = {s.type_id: s.value for s in r.strands}
    assert sm["microbe.disease.count"] >= 1
    assert sm["microbe.disease.names"], "expected at least one disease name"
    # the full blob carries the joined publication record
    assert any(rec.get("publication") for rec in sm["microbe.disease.records"])

    # a taxid Disbiome does not track resolves to NO_MATCH, not an error
    miss = await weaver.execute_batch(
        "disbiome.list_diseases",
        [StrandSet.from_strands("e", [Strand("ncbi.taxon.id", 999999999)])],
        requested_outputs=frozenset({"microbe.disease.names"}),
        backend="local",
    )
    assert miss[0].status is WeaveStatus.NO_MATCH
