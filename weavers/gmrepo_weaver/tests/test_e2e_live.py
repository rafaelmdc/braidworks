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
from gmrepo_weaver.acquisition import AcquisitionPolicy, _AcquisitionClient
from gmrepo_weaver.backends.local import GmrepoLocalBackend
from gmrepo_weaver.setup import (
    _fetch_profiles,
    _fetch_run_ids,
    _overview_rows,
    _post,
    _taxon_associations,
    write_db,
)
from gmrepo_weaver.weaver import GmrepoWeaver

pytestmark = pytest.mark.skipif(
    not os.environ.get("BRAIDWORKS_RUN_LIVE"),
    reason="live E2E; set BRAIDWORKS_RUN_LIVE=1 (hits the GMrepo API)",
)

_BACTEROIDES = 816  # a genus present in every gut-metagenome phenotype set


async def test_live_minibuild_and_resolve(tmp_path: Path):
    post = _AcquisitionClient(_post, AcquisitionPolicy(max_calls=12))
    overview = _overview_rows(post("get_all_gut_microbes", {}))
    assert len(overview) > 100, "expected a large gut-microbe universe"
    assert any(r["ncbi_taxon_id"] == _BACTEROIDES for r in overview)

    picked = [r for r in overview if r["ncbi_taxon_id"] == _BACTEROIDES]
    payload = post(
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

    assert 2 <= post.calls <= 12 and not post.budget_exhausted

    # a taxid GMrepo does not track resolves to NO_MATCH, not an error
    miss = await weaver.execute_batch(
        "gmrepo.list_abundances",
        [StrandSet.from_strands("e", [Strand("ncbi.taxon.id", 999999999)])],
        requested_outputs=frozenset({"microbe.abundance.count"}),
        backend="local",
    )
    skip_if_transient(miss[0])
    assert miss[0].status is WeaveStatus.NO_MATCH


async def test_live_sample_profiles_minibuild(tmp_path: Path):
    """The per-run sample-profile path: list runs for a phenotype + fetch a few profiles."""
    mesh_id = "D003924"  # Crohn Disease — a well-sampled phenotype
    post = _AcquisitionClient(_post, AcquisitionPolicy(max_calls=12))
    run_ids = _fetch_run_ids(post, mesh_id, max_runs=3)
    assert run_ids, "expected the *Limit run-listing route to return run ids"

    profiles = _fetch_profiles(post, [mesh_id], max_runs=3)
    assert profiles, "expected per-run taxonomic profiles with relative abundances"
    assert 3 <= post.calls <= 12 and not post.budget_exhausted
    assert all(0.0 <= p["relative_abundance"] <= 100.0 for p in profiles)
    assert len({p["run_id"] for p in profiles}) >= 1

    db = tmp_path / "gmrepo.sqlite"
    write_db(db, overview=[], associations=[], phenotypes=[], sample_profiles=profiles)
    weaver = GmrepoWeaver({"local": GmrepoLocalBackend(db)})
    out = await weaver.execute_batch(
        "gmrepo.sample_profiles",
        [StrandSet.from_strands("e", [Strand("disease.mesh.id", mesh_id)])],
        requested_outputs=frozenset({"microbe.abundance.sample_profiles"}),
        backend="local",
    )
    r = out[0]
    skip_if_transient(r)
    assert r.status is WeaveStatus.OK
    profile = {s.type_id: s.value for s in r.strands}["microbe.abundance.sample_profiles"]
    assert profile["mesh_id"] == mesh_id
    assert profile["n_runs"] >= 1
    assert profile["profiles"]


async def test_live_run_listing_retains_observed_metadata():
    scope = {}
    post = _AcquisitionClient(_post, AcquisitionPolicy(max_calls=2))
    ids = _fetch_run_ids(post, "D003093", max_runs=1, coverage=scope)
    assert ids and post.calls == 1
    row = scope["run_metadata"][ids[0]]
    assert row["run_id"] == ids[0]
    assert row["project_id"] and row["sample_id"]
    assert "QCStatus" in row
    assert scope["selected_runs"] == 1 and scope["cap"] == 1


async def test_live_selection_filter_and_run_drill_down(tmp_path):
    scope = {}
    post = _AcquisitionClient(_post, AcquisitionPolicy(max_calls=4))
    ids = _fetch_run_ids(post, "D003093", max_runs=1, coverage=scope, filters={"country": "China"})
    assert ids and scope["run_metadata"][ids[0]]["country"] == "China"
    db = tmp_path / "run.sqlite"
    write_db(
        db,
        overview=[],
        associations=[],
        phenotypes=[],
        acquisition={"profiles": {"D003093": scope}, "taxa": {}},
    )
    backend = GmrepoLocalBackend(db)
    described = (
        await backend.fetch(
            "gmrepo.describe_run",
            [{"metagenome.run_id": ids[0]}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"run"}),
        )
    )[0]
    assert described.found
    assert described.values["microbe.abundance.run"]["source_evidence"][0]["metadata"]["project_id"]
