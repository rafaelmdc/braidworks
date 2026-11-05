"""tools/release_tags.py: derive <name>-v<version> tags from package pyprojects."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_TOOL = Path(__file__).resolve().parents[2] / "tools" / "release_tags.py"
_spec = importlib.util.spec_from_file_location("release_tags", _TOOL)
release_tags = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_tags)


def _pkg(root: Path, rel: str, name: str, version: str) -> None:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\n'
    )


def test_expected_tags_derives_name_v_version(tmp_path):
    _pkg(tmp_path, "braidworks-core", "braidworks-core", "0.2.0")
    _pkg(tmp_path, "weavers/foo_weaver", "foo_weaver", "1.2.3")
    tags = {tag for tag, _ in release_tags.expected_tags(tmp_path)}
    assert "braidworks-core-v0.2.0" in tags
    assert "foo_weaver-v1.2.3" in tags


def test_expected_tags_skips_packages_without_version(tmp_path):
    d = tmp_path / "weavers" / "bar_weaver"
    d.mkdir(parents=True)
    (d / "pyproject.toml").write_text('[project]\nname = "bar_weaver"\n')  # no version
    assert release_tags.expected_tags(tmp_path) == []


def test_expected_tags_ignores_dir_without_pyproject(tmp_path):
    (tmp_path / "weavers" / "empty").mkdir(parents=True)
    assert release_tags.expected_tags(tmp_path) == []


def test_parse_ls_remote_extracts_names_and_drops_peeled():
    # real `git ls-remote --tags` shape: "<sha>\trefs/tags/<name>", with ^{} peel lines.
    text = (
        "abc123\trefs/tags/braidworks-core-v0.6.0\n"
        "def456\trefs/tags/braidworks-core-v0.6.0^{}\n"
        "789aaa\trefs/tags/uniprot_weaver-v0.1.2\n"
    )
    assert release_tags._parse_ls_remote(text) == {
        "braidworks-core-v0.6.0",
        "uniprot_weaver-v0.1.2",
    }


def test_existing_tags_unions_local_and_remote(monkeypatch):
    # a tag already on the remote must count as existing, so it is never re-created.
    monkeypatch.setattr(release_tags, "_local_tags", lambda: {"a-v1"})
    monkeypatch.setattr(release_tags, "_remote_tags", lambda: {"b-v2"})
    assert release_tags._existing_tags() == {"a-v1", "b-v2"}
