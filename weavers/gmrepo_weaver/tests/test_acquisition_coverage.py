"""Persist failures, empty profiles and capped scope, rather than inferring absence."""

import json
import sqlite3
import urllib.error

import pytest
from gmrepo_weaver import setup
from gmrepo_weaver.acquisition import AcquisitionPolicy

FAST_POLICY = AcquisitionPolicy(requests_per_second=100000, max_attempts=1)
from gmrepo_weaver.backends.local import GmrepoLocalBackend


def post(endpoint, body):
    if endpoint == "get_all_gut_microbes":
        return {"all_genus": [], "all_species": [{"ncbi_taxon_id": i} for i in [1, 2, 3]]}
    if endpoint == "get_all_phenotypes":
        return {"phenotypes": [{"disease": "M", "term": "Condition", "valid_runs": 100}]}
    if endpoint == setup._TAXON_ENDPOINT:
        if body["ncbi_taxon_id"] == 1:
            raise urllib.error.URLError("taxon unavailable")
        return {"phenotypes_associated_with_taxon": []}
    if endpoint == setup._RUNS_ENDPOINT:
        return [{"run_id": r} for r in ["populated", "empty", "failed"]][: body["limit"]]
    if endpoint == setup._PROFILE_ENDPOINT:
        if body["run_id"] == "failed":
            raise urllib.error.URLError("profile unavailable")
        return {
            "species": (
                [{"ncbi_taxon_id": 2, "relative_abundance": 10}]
                if body["run_id"] == "populated"
                else []
            ),
            "genus": [],
        }
    raise AssertionError(endpoint)


async def fetch(backend, capability, query):
    return (
        await backend.fetch(
            capability, [query], requested_outputs=frozenset(), groups_to_compute=frozenset()
        )
    )[0]


async def test_failed_taxon_does_not_become_zero_associations(tmp_path):
    path = tmp_path / "source.sqlite"
    setup._build(path, post=post, acquisition_policy=FAST_POLICY)
    backend = GmrepoLocalBackend(path)
    failed = await fetch(backend, "gmrepo.list_abundances", {"ncbi.taxon.id": 1})
    assert failed.error and not failed.found
    empty = await fetch(backend, "gmrepo.list_abundances", {"ncbi.taxon.id": 2})
    assert empty.found and empty.values["microbe.abundance.count"] == 0
    assert empty.values["microbe.abundance.coverage"]["complete"] is True
    with sqlite3.connect(path) as con:
        manifest = json.loads(
            con.execute("SELECT value FROM meta WHERE key='acquisition'").fetchone()[0]
        )
        assert manifest["taxa"]["1"]["status"] == "failed"
        assert manifest["taxa"]["2"]["status"] == "empty"


async def test_profiles_report_selected_empty_failed_and_real_denominators(tmp_path):
    path = tmp_path / "source.sqlite"
    setup._build(
        path,
        post=post,
        profile_phenotypes=["M"],
        profile_max_runs=3,
        acquisition_policy=FAST_POLICY,
    )
    record = await fetch(
        GmrepoLocalBackend(path), "gmrepo.sample_profiles", {"disease.mesh.id": "M"}
    )
    value = record.values["microbe.abundance.sample_profiles"]
    coverage = value["coverage"]
    assert value["n_runs"] == value["n_runs_with_rows"] == 1
    assert coverage["selected_runs"] == 3
    assert coverage["fetched_runs"] == 2 and coverage["empty_runs"] == coverage["failed_runs"] == 1
    assert coverage["capped"] and not coverage["complete"]
    assert value["denominator"] == {"fetched_runs": 2, "cohort_total_runs": 100}
    assert coverage["runs"]["failed"]["error"]
    missing = await fetch(
        GmrepoLocalBackend(path), "gmrepo.sample_profiles", {"disease.mesh.id": "unrequested"}
    )
    assert missing.error


async def test_successful_empty_profile_is_known_empty(tmp_path):
    def empty_post(endpoint, body):
        if endpoint == setup._RUNS_ENDPOINT:
            return [{"run_id": "empty"}]
        return post(endpoint, body)

    path = tmp_path / "source.sqlite"
    setup._build(
        path,
        post=empty_post,
        profile_phenotypes=["M"],
        profile_max_runs=3,
        acquisition_policy=FAST_POLICY,
    )
    record = await fetch(
        GmrepoLocalBackend(path), "gmrepo.sample_profiles", {"disease.mesh.id": "M"}
    )
    value = record.values["microbe.abundance.sample_profiles"]
    assert record.found and value["profiles"] == []
    assert value["coverage"]["complete"] and value["denominator"]["fetched_runs"] == 1


def test_programming_fault_in_worker_is_not_swallowed():
    def broken(endpoint, body):
        if endpoint == setup._TAXON_ENDPOINT:
            raise RuntimeError("bug")
        return post(endpoint, body)

    with pytest.raises(RuntimeError, match="bug"):
        setup._fetch_tables(broken)
