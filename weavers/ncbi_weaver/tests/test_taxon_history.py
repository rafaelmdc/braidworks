"""History distinguishes current, merged, deleted and unavailable source evidence."""

import io
import tarfile

import pytest
from braidworks.core import Strand, StrandSet, WeaveStatus
from ncbi_weaver.backends.local import LocalTaxonomyBackend
from ncbi_weaver.fixture import NAMES_DMP, NODES_DMP, build_fixture_db
from ncbi_weaver.weaver import NCBITaxonWeaver
from taxonomy_resolver.build import build_taxonomy_database
from taxonomy_resolver.history import parse_history


@pytest.mark.parametrize(
    "merged,deleted",
    [
        ([["10", "11"], ["11", "10"]], []),
        ([["10", "853"], ["10", "854"]], []),
        ([], [["11"], ["11"]]),
        ([["10", "853"]], [["10"]]),
    ],
)
def test_invalid_history_is_rejected(merged, deleted):
    with pytest.raises(ValueError):
        parse_history(merged, deleted)


async def test_history_dump_chain_deleted_unknown_and_existing_current_lookup(tmp_path):
    archive = tmp_path / "history.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, text in [
            ("nodes.dmp", NODES_DMP),
            ("names.dmp", NAMES_DMP),
            ("merged.dmp", "900\t|\t901\t|\n901\t|\t853\t|\n"),
            ("delnodes.dmp", "902\t|\n"),
        ]:
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    path = tmp_path / "taxonomy.sqlite"
    build_taxonomy_database(archive, path)
    backend = LocalTaxonomyBackend(path)
    async with NCBITaxonWeaver({"local": backend}) as weaver:
        results = await weaver.execute_batch(
            "ncbi.describe_taxon_history",
            [
                StrandSet.from_strands(str(i), [Strand("ncbi.taxon.id", i)])
                for i in [853, 900, 902, 903]
            ],
            requested_outputs=frozenset({"ncbi.taxon.history"}),
            backend="local",
        )
        assert all(r.status is WeaveStatus.OK for r in results)
        values = [{s.type_id: s.value for s in r.strands}["ncbi.taxon.history"] for r in results]
        assert [v["status"] for v in values] == ["current", "merged", "deleted", "unknown"]
        assert values[1]["current_taxid"] == 853 and values[1]["requested_taxid"] == 900
        assert values[1]["merge_chain"] == [900, 901, 853]
        assert all(v["current_taxid"] is None for v in values[2:])
        assert all(v["source_dump_sha256"] for v in values)
        current = (await backend.resolve("ncbi.describe_taxon", [853], need_lineage=False))[0]
        assert current.taxid == 853


async def test_missing_history_files_mean_unavailable_not_deleted(tmp_path):
    backend = LocalTaxonomyBackend(build_fixture_db(tmp_path))
    results = await backend.describe_taxon_history([{"ncbi.taxon.id": i} for i in [853, 902]])
    history = results[1].values["ncbi.taxon.history"]
    assert history["status"] == "unknown" and history["current_taxid"] is None
    assert history["history_available"] == {"merged": False, "deleted": False}
    assert results[0].values["ncbi.taxon.history"]["status"] == "current"


def test_invalid_history_preserves_existing_database(tmp_path):
    path = build_fixture_db(tmp_path)
    before = path.read_bytes()
    archive = tmp_path / "bad-history.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, text in [
            ("nodes.dmp", NODES_DMP),
            ("names.dmp", NAMES_DMP),
            ("merged.dmp", "900\t|\t901\t|\n901\t|\t900\t|\n"),
        ]:
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError, match="cycle"):
        build_taxonomy_database(archive, path)
    assert path.read_bytes() == before
