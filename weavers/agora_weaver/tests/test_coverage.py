"""Model acquisition outcomes survive the build and distinguish empty from unavailable."""

import zipfile

import pytest
from agora_weaver import dataset
from agora_weaver.backends.local import AgoraLocalBackend
from agora_weaver.weaver import AgoraWeaver
from braidworks.core import Strand, StrandSet, WeaveStatus


def test_manifest_records_good_empty_and_malformed_models(tmp_path):
    archive = tmp_path / "models.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("good.xml", '<sbml><model><reaction id="R_one"/></model></sbml>')
        zf.writestr("empty.xml", "<sbml><model/></sbml>")
        zf.writestr("broken.xml", '<sbml><reaction id="R_partial"/>')
    target = tmp_path / "reactions.sqlite"
    dataset.build_reaction_db(archive, [], target, content_hash="archive")
    with dataset.open_ro(target) as con:
        manifest = {
            r[0]: r[1:]
            for r in con.execute(
                "SELECT reconstruction, status, reaction_count, error FROM model_coverage"
            )
        }
        assert manifest["good"] == ("processed", 1, None)
        assert manifest["empty"] == ("processed", 0, None)
        assert manifest["broken"][0] == "skipped" and manifest["broken"][2]
        assert dataset.reactions_for(con, ["empty"]) == []
        for identifier in ["broken", "missing"]:
            with pytest.raises(dataset.IncompleteModelCoverage):
                dataset.reactions_for(con, [identifier])
        assert not con.execute("SELECT 1 FROM reaction WHERE reconstruction='broken'").fetchall()
        meta = dict(con.execute("SELECT key, value FROM meta"))
        assert meta["models_processed"] == "2" and meta["models_skipped"] == "1"


async def test_requested_missing_reactions_fail_without_completed_groups(tmp_path):
    weaver = AgoraWeaver({"local": AgoraLocalBackend(tmp_path / "missing.sqlite")})
    inputs = [StrandSet.from_strands("one", [Strand("ncbi.taxon.id", "592010")])]
    result = (
        await weaver.execute_batch(
            "describe_metabolic_reconstruction",
            inputs,
            requested_outputs=frozenset({"microbe.metabolism.reactions"}),
            backend="local",
        )
    )[0]
    assert result.status is WeaveStatus.ERROR and not result.computed_groups
    result = (
        await weaver.execute_batch(
            "describe_metabolic_reconstruction",
            inputs,
            requested_outputs=frozenset({"microbe.metabolism.reconstruction"}),
            backend="local",
        )
    )[0]
    assert result.status is WeaveStatus.OK
