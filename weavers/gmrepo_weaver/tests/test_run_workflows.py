"""Run identity, source evidence and selection precede display/profile limits."""

from gmrepo_weaver.backends.local import GmrepoLocalBackend
from gmrepo_weaver.fixture import _ASSOCIATIONS, _OVERVIEW, _PHENOTYPES, _SAMPLE_PROFILES
from gmrepo_weaver.setup import _fetch_run_ids, write_db


def test_metadata_selection_occurs_before_run_cap_and_unknown_never_matches():
    calls = []
    source = [
        {"run_id": "R0", "country": None},
        {"run_id": "R1", "country": "France"},
        {"run_id": "R2", "country": "China"},
        {"run_id": "R3", "country": "China"},
    ]

    def post(endpoint, body):
        calls.append(dict(body))
        return source[body["skip"] : body["skip"] + body["limit"]]

    scope = {}
    ids = _fetch_run_ids(post, "D003093", 1, scope, filters={"country": "China"})
    assert ids == ["R2"]
    assert scope["scanned_runs"] == 3 and scope["selected_runs"] == 1
    assert scope["selection_filters"] == {"country": "China"}
    assert scope["capped"]
    assert [c["skip"] for c in calls] == [0, 1, 2]


async def test_run_pair_phenotype_bridge_and_failed_empty_profiles(tmp_path):
    metadata = {
        "ERRFIX01": {"run_id": "ERRFIX01", "country": "China", "QCStatus": 1},
        "ERRFIX02": {"run_id": "ERRFIX02", "country": None},
        "EMPTY": {"run_id": "EMPTY", "country": "China"},
        "FAILED": {"run_id": "FAILED", "country": "China"},
    }
    path = tmp_path / "runs.sqlite"
    scope = {
        "status": "acquired",
        "run_metadata": metadata,
        "capped": True,
        "runs": {"EMPTY": {"status": "empty"}, "FAILED": {"status": "failed", "error": "timeout"}},
    }
    write_db(
        path,
        overview=_OVERVIEW,
        associations=_ASSOCIATIONS,
        phenotypes=_PHENOTYPES,
        sample_profiles=_SAMPLE_PROFILES,
        acquisition={"profiles": {"D003093": scope}, "taxa": {}},
    )
    backend = GmrepoLocalBackend(path)

    async def fetch(cap, query, params=None):
        return (
            await backend.fetch(
                cap,
                [query],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(),
                params=params,
            )
        )[0]

    listed = await fetch("gmrepo.list_runs", {"disease.mesh.id": "D003093"}, {"country": "China"})
    assert listed.values["metagenome.run_id"] == ["EMPTY", "ERRFIX01", "FAILED"]
    assert listed.values["microbe.abundance.run_listing"]["coverage"]["capped"]
    run = await fetch("gmrepo.describe_run", {"metagenome.run_id": "ERRFIX01"})
    assert run.found and len(run.values["microbe.abundance.run"]["profiles"]) == 2
    for rid, status in [("EMPTY", "empty"), ("FAILED", "failed")]:
        record = await fetch("gmrepo.describe_run", {"metagenome.run_id": rid})
        assert record.found and not record.values["microbe.abundance.run"]["profiles"]
        assert (
            record.values["microbe.abundance.run"]["source_evidence"][0]["profile_outcome"][
                "status"
            ]
            == status
        )
    assert not (await fetch("gmrepo.describe_run", {"metagenome.run_id": "MISSING"})).found
    disease = await fetch("gmrepo.list_phenotypes", {"ncbi.taxon.id": 216851})
    assert disease.values["disease.mesh.id"] == ["D003093", "D003424"]
    metadata_missing = await fetch(
        "gmrepo.list_runs", {"disease.mesh.id": "MISSING"}, {"country": "China"}
    )
    assert metadata_missing.error


def test_invalid_builder_filters_fail_before_any_acquisition(monkeypatch):
    import pytest
    from braidworks.core import BackendConfigurationError
    from gmrepo_weaver import factory

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid configuration must not acquire data")

    monkeypatch.setattr(factory, "ensure_gmrepo_db", forbidden)
    for filters in [{"QCStatus": True}, {"country": 1}, {"unsupported": "value"}]:
        with pytest.raises(BackendConfigurationError):
            factory.build_gmrepo_weaver_configured(profile_filters=filters)
