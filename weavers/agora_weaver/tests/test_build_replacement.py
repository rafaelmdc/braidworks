"""Complete AGORA replacement, provenance, cleanup and bounded XML parsing."""

import hashlib
import json
import tracemalloc
import zipfile
from unittest.mock import patch

import pytest
from agora_weaver import dataset, setup


def archive(path, rid="model", reaction="one", empty=False):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            f"{rid}.xml",
            "<sbml><model>"
            + ("" if empty else f'<reaction id="R_{reaction}"/>')
            + "</model></sbml>",
        )
    return path


def build(path, target, **kwargs):
    return dataset.build_reaction_db(
        path, [("one", "system", None, None, None)], target, content_hash="archive-digest", **kwargs
    )


def test_replacement_removes_stale_rows_and_records_annotations(tmp_path):
    path = archive(tmp_path / "models.zip")
    target = tmp_path / "reactions.sqlite"
    build(path, target)
    archive(path, rid="new-model", reaction="two")
    info = [("two", "new-system", "1.2.3.4", None, None)]
    assert (
        dataset.build_reaction_db(
            path,
            iter(info),
            target,
            content_hash="new-archive",
            annotation_source="https://example.test/reactions",
            sbml_source="https://example.test/models.zip",
        )
        == 1
    )
    with dataset.open_ro(target) as con:
        assert con.execute("SELECT reconstruction, abbreviation FROM reaction").fetchall() == [
            ("new-model", "two")
        ]
        assert con.execute("SELECT abbreviation FROM rxn_info").fetchall() == [("two",)]
        meta = dict(con.execute("SELECT key, value FROM meta"))
    digest = hashlib.sha256(
        (json.dumps(info[0], separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    assert meta["annotation_sha256"] == digest
    assert meta["annotation_rows"] == "1"
    assert meta["annotation_source"] == "https://example.test/reactions"
    assert meta["sbml_source"] == "https://example.test/models.zip"
    assert meta["content_hash"] == "new-archive"
    assert setup.db_is_valid(target)


@pytest.mark.parametrize("failure", ["archive", "annotation", "empty", "publication"])
@pytest.mark.parametrize("existing", [True, False])
def test_failure_preserves_target_and_cleans_staging(tmp_path, failure, existing):
    path = archive(tmp_path / "models.zip")
    target = tmp_path / "reactions.sqlite"
    if existing:
        build(path, target)
    before = target.read_bytes() if existing else None

    def annotations():
        yield ("two", None, None, None, None)
        raise ValueError("annotation failure")

    if failure == "archive":
        path.write_bytes(b"invalid zip")
    if failure == "empty":
        archive(path, empty=True)
    if failure == "publication":
        with (
            patch("braidworks.core.localdb.os.replace", side_effect=OSError("publish")),
            pytest.raises(OSError),
        ):
            build(path, target)
    else:
        with pytest.raises((ValueError, zipfile.BadZipFile)):
            dataset.build_reaction_db(
                path, annotations() if failure == "annotation" else [], target, content_hash="new"
            )
    assert (target.read_bytes() if target.exists() else None) == before
    assert all(
        p.name in {path.name, target.name, target.name + ".lock"} for p in tmp_path.iterdir()
    )


def test_acquisition_removes_download_even_when_annotations_fail(tmp_path):
    target = tmp_path / "reactions.sqlite"

    def download(_url, destination, **_kwargs):
        archive(destination)

    with (
        patch.object(setup, "_download", side_effect=download),
        patch.object(setup, "_fetch_reaction_crosswalk", side_effect=ValueError("upstream")),
        pytest.raises(ValueError),
    ):
        setup._build_reaction_db(target, sbml_url="source", reactions_api="annotations")
    assert not (tmp_path / "AGORA2_SBML.zip").exists()
    assert not target.exists()


def test_xml_parser_releases_nonreaction_elements(tmp_path):
    def peak(count):
        path = tmp_path / f"model-{count}.xml"
        with path.open("w") as handle:
            handle.write("<sbml><model><listOfSpecies>")
            for index in range(count):
                handle.write(f'<species id="s{index}"><annotation>detail</annotation></species>')
            handle.write('</listOfSpecies><reaction id="R_one"/></model></sbml>')
        tracemalloc.start()
        try:
            with path.open("rb") as handle:
                assert list(dataset.iter_sbml_reactions(handle)) == ["one"]
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    small, large = peak(1000), peak(20000)
    assert large < small * 3 + 300_000
