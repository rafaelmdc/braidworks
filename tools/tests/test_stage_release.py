"""Release selection must fail closed before artifacts can be published."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage_release import stage_release


class ReleaseSelectionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        for name in ("braidworks-core", "weaverkit", "braidworks-arq"):
            project = self.root / name
            project.mkdir()
            (project / "pyproject.toml").write_text(f'[project]\nname="{name}"\nversion="1.2.3"\n')
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        for name in (
            "braidworks_core-1.2.3-py3-none-any.whl",
            "braidworks_core-1.2.3.tar.gz",
            "weaverkit-1.2.3-py3-none-any.whl",
        ):
            (self.artifacts / name).write_text(name)
        self.destination = self.root / "staged"

    def test_only_selected_package_is_staged(self):
        files = stage_release(
            self.root,
            "braidworks-core",
            self.artifacts,
            self.destination,
            ref="refs/tags/braidworks-core-v1.2.3",
        )
        self.assertEqual(len(files), 2)
        self.assertEqual(set(files), set(self.destination.iterdir()))
        for path in files:
            self.assertEqual(path.read_text(), path.name)

    def test_branch_wrong_package_and_wrong_version_refs_are_rejected(self):
        for ref in (
            "refs/heads/main",
            "refs/tags/weaverkit-v1.2.3",
            "refs/tags/braidworks-core-v1.2.4",
        ):
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, "publishing requires"):
                stage_release(
                    self.root, "braidworks-core", self.artifacts, self.destination, ref=ref
                )
            self.assertFalse(self.destination.exists())

    def test_unknown_package_cannot_be_a_path(self):
        with self.assertRaisesRegex(ValueError, "unknown workspace"):
            stage_release(self.root, "../braidworks-core", self.artifacts, self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_artifact_does_not_create_output(self):
        with self.assertRaises(FileNotFoundError):
            stage_release(self.root, "weaverkit", self.artifacts, self.destination)
        self.assertFalse(self.destination.exists())

    def test_existing_destination_is_never_overwritten(self):
        self.destination.mkdir()
        sentinel = self.destination / "keep"
        sentinel.write_text("original")
        with self.assertRaises(FileExistsError):
            stage_release(self.root, "braidworks-core", self.artifacts, self.destination)
        self.assertEqual(sentinel.read_text(), "original")
        self.assertEqual(list(self.destination.iterdir()), [sentinel])
