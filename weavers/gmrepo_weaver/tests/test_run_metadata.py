"""Run listing evidence survives empty/failed profiles without extra requests."""

import copy

from gmrepo_weaver import setup
from gmrepo_weaver.backends.local import GmrepoLocalBackend
from tests.test_acquisition_coverage import FAST_POLICY, post


async def test_metadata_survives_profile_outcomes_and_preserves_default(tmp_path):
    calls = []

    def metadata_post(endpoint, body):
        calls.append(endpoint)
        rows = post(endpoint, body)
        if endpoint == setup._RUNS_ENDPOINT:
            return [
                {
                    **row,
                    "sample_id": "SRS-example",
                    "project_id": "PRJNA-example",
                    "host_age": None,
                    "QCStatus": 1,
                }
                for row in rows
            ]
        return rows

    path = tmp_path / "metadata.sqlite"
    setup._build(
        path,
        post=metadata_post,
        profile_phenotypes=["M"],
        profile_max_runs=3,
        acquisition_policy=FAST_POLICY,
    )
    assert calls.count(setup._RUNS_ENDPOINT) == 1
    assert calls.count(setup._PROFILE_ENDPOINT) == 3
    backend = GmrepoLocalBackend(path)

    async def lookup(groups):
        return (
            await backend.fetch(
                "gmrepo.sample_profiles",
                [{"disease.mesh.id": "M"}],
                requested_outputs=frozenset(),
                groups_to_compute=frozenset(groups),
            )
        )[0]

    default = await lookup({"profiles"})
    before = copy.deepcopy(default.values["microbe.abundance.sample_profiles"])
    assert "run_metadata" not in before["coverage"]
    both = await lookup({"profiles", "metadata"})
    assert both.values["microbe.abundance.sample_profiles"] == before
    metadata = (await lookup({"metadata"})).values["microbe.abundance.run_metadata"]
    assert metadata["available"]
    assert [row["run_id"] for row in metadata["records"]] == ["empty", "failed", "populated"]
    assert all(row["host_age"] is None for row in metadata["records"])
    assert metadata["coverage"]["failed_runs"] == 1
    assert metadata["coverage"]["empty_runs"] == 1
    assert metadata["coverage"]["selected_runs"] == 3
    assert metadata["coverage"]["cohort_total_runs"] == 100
    assert metadata["coverage"]["capped"]
    assert "microbe.abundance.sample_profiles" not in (await lookup({"metadata"})).values
