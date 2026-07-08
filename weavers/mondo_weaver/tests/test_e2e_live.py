"""Opt-in live E2E: download the real MONDO OBO, build the DB, and resolve a MeSH id.

Self-skips unless BRAIDWORKS_RUN_LIVE=1 (it downloads the ~53 MB OBO release and builds a
local SQLite in a temp dir). Run after touching setup.py or when MONDO changes its format:

    BRAIDWORKS_RUN_LIVE=1 make -C weavers/mondo_weaver test-live
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from braidworks.core import Strand, StrandSet, WeaveStatus, skip_if_transient

from mondo_weaver.backends.local import MondoLocalBackend
from mondo_weaver.setup import ensure_mondo_db
from mondo_weaver.weaver import MondoWeaver

pytestmark = pytest.mark.skipif(
    not os.environ.get("BRAIDWORKS_RUN_LIVE"),
    reason="live E2E; set BRAIDWORKS_RUN_LIVE=1 (downloads the ~53 MB MONDO OBO)",
)

_UC_MESH = "D003093"  # ulcerative colitis, a stable MONDO:equivalentTo MeSH xref


async def test_live_build_and_resolve(tmp_path: Path):
    db = ensure_mondo_db(tmp_path / "mondo.sqlite", auto=True)
    weaver = MondoWeaver({"local": MondoLocalBackend(db)})

    out = await weaver.execute_batch(
        "mondo.lookup_by_mesh",
        [StrandSet.from_strands("e", [Strand("disease.mesh.id", _UC_MESH)])],
        requested_outputs=frozenset(
            {"disease.mondo.id", "disease.ontology.name", "disease.ontology.ancestors"}
        ),
        backend="local",
    )
    r = out[0]
    skip_if_transient(r)
    assert r.status is WeaveStatus.OK
    sm = {s.type_id: s.value for s in r.strands}
    assert sm["disease.mondo.id"] == "MONDO:0005101"
    assert "colitis" in sm["disease.ontology.name"].lower()
    # a real lineage: the term plus several is-a ancestors up to a root
    ids = [a["mondo_id"] for a in sm["disease.ontology.ancestors"]]
    assert ids[0] == "MONDO:0005101"
    assert len(ids) >= 3
    assert "MONDO:0000001" in ids  # the ontology root

    miss = await weaver.execute_batch(
        "mondo.lookup_by_mesh",
        [StrandSet.from_strands("e", [Strand("disease.mesh.id", "D000000000")])],
        requested_outputs=frozenset({"disease.ontology.name"}),
        backend="local",
    )
    skip_if_transient(miss[0])
    assert miss[0].status is WeaveStatus.NO_MATCH
