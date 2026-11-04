"""Metadata routing stays offline and qualifies model identity by source release."""

from agora_weaver import dataset
from agora_weaver.backends.local import AgoraLocalBackend

MODEL = "Abiotrophia_defectiva_ATCC_49176"
KEY = f"{dataset.CROSSWALK_RELEASE}:{MODEL}"


async def test_exact_metadata_reports_missing_cached_and_unverified_release(tmp_path, monkeypatch):
    from agora_weaver import setup

    def forbidden(*args, **kwargs):
        raise AssertionError("metadata queries must not acquire models")

    monkeypatch.setattr(setup, "ensure_model_sbml", forbidden)
    backend = AgoraLocalBackend(sbml_cache_dir=tmp_path)
    query = [{"microbe.agora.reconstruction_id": KEY}]

    async def metadata(backend):
        return (
            await backend.fetch(
                "describe_reconstruction",
                query,
                requested_outputs=frozenset(),
                groups_to_compute=frozenset({"identity", "artifact"}),
            )
        )[0]

    missing = await metadata(backend)
    assert missing.found
    assert missing.values["microbe.agora.artifact"]["status"] == "consent_required"
    identity = missing.values["microbe.agora.reconstruction"]
    assert identity["source_associations"][0]["gcf_id"] == "GCF_000160075.2"
    (tmp_path / f"{MODEL}.xml").write_text(f'<sbml><model id="{MODEL}"/></sbml>')
    cached = await metadata(AgoraLocalBackend(sbml_cache_dir=tmp_path))
    artifact = cached.values["microbe.agora.artifact"]
    assert artifact["sha256"] and artifact["model_id"] == MODEL
    assert artifact["release_verified"] is False
    mismatch = (
        await backend.fetch(
            "describe_reconstruction",
            [{"microbe.agora.reconstruction_id": "AGORA2-v1:" + MODEL}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"identity"}),
        )
    )[0]
    assert mismatch.error


async def test_listing_fan_ids_are_uncapped_and_never_acquire_artifacts(tmp_path, monkeypatch):
    rows = [{"reconstruction_id": f"strain_{i:02}", "gcf_id": "GCF_000160075.2"} for i in range(12)]
    monkeypatch.setattr(dataset, "reconstructions_for", lambda taxid: rows)
    record = (
        await AgoraLocalBackend(sbml_cache_dir=tmp_path, auto_download_models=True).fetch(
            "list_reconstructions",
            [{"ncbi.taxon.id": "592010"}],
            requested_outputs=frozenset(),
            groups_to_compute=frozenset({"reconstructions"}),
        )
    )[0]
    assert len(record.values["microbe.agora.reconstruction_id"]) == 12
    assert len(record.values["microbe.agora.reconstructions"]) == 10
    assert record.values["microbe.agora.coverage"]["observed_count"] == 12
    assert list(tmp_path.iterdir()) == []
