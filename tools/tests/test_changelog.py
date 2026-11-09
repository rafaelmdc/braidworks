"""Changelogs: entries accumulate under Unreleased; a version bump closes them."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import changelog

TODAY = "2030-01-02"


class ChangelogTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "Test")
        self.project("braidworks-core", "braidworks-core", "0.1.0")
        self.project("weavers/a_weaver", "a_weaver", "1.0.0")
        self.commit(
            "braidworks-core/x.py", "Merge pull request #1 from me/start\n\nFirst core feature"
        )
        self.commit("weavers/a_weaver/x.py", "feat: the weaver (#2)")
        self.git("tag", "braidworks-core-v0.1.0")
        self.git("tag", "a_weaver-v1.0.0")

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout

    def project(self, folder, name, version):
        path = self.root / folder
        path.mkdir(parents=True, exist_ok=True)
        (path / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')

    def commit(self, relative, message):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.read_text() + "x" if path.exists() else "x")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def read(self, relative):
        return (self.root / relative).read_text()

    def test_released_versions_get_dated_sections_with_pr_titles(self):
        changelog.write(self.root, today=TODAY)
        core = self.read("braidworks-core/CHANGELOG.md")
        self.assertIn("## 0.1.0 (", core)
        self.assertIn("- First core feature (#1)", core)
        self.assertNotIn("Unreleased", core)  # nothing pending
        self.assertIn("- feat: the weaver (#2)", self.read("weavers/a_weaver/CHANGELOG.md"))

    def test_changes_accumulate_under_unreleased_until_a_bump(self):
        self.commit("braidworks-core/y.py", "Merge pull request #3 from me/more\n\nSecond change")
        changelog.write(self.root, today=TODAY)
        core = self.read("braidworks-core/CHANGELOG.md")
        self.assertIn("## Unreleased\n\n- Second change (#3)", core)

        self.project("braidworks-core", "braidworks-core", "0.2.0")
        self.commit("braidworks-core/z.py", "Merge pull request #4 from me/bump\n\nRelease 0.2")
        changelog.write(self.root, today=TODAY)
        core = self.read("braidworks-core/CHANGELOG.md")
        self.assertNotIn("Unreleased", core)
        self.assertIn(f"## 0.2.0 ({TODAY})\n\n- Release 0.2 (#4)\n- Second change (#3)", core)

    def test_the_combined_changelog_lists_only_packages_with_changes(self):
        self.commit("braidworks-core/y.py", "Merge pull request #3 from me/more\n\nSecond change")
        changelog.write(self.root, today=TODAY)
        combined = self.read("CHANGELOG.md")
        unreleased = combined.split("## Unreleased\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("### braidworks-core\n\n- Second change (#3)", unreleased)
        self.assertNotIn("a_weaver", unreleased)  # no pending changes, left out
        self.assertIn("### a_weaver 1.0.0", combined)

    def test_changelog_commits_are_not_entries(self):
        changelog.write(self.root, today=TODAY)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore(changelog): update [skip ci]")
        self.assertEqual(changelog.write(self.root, today=TODAY), [])

    def test_notes_give_a_tags_section_and_compare_link(self):
        self.project("braidworks-core", "braidworks-core", "0.2.0")
        self.commit("braidworks-core/z.py", "Merge pull request #4 from me/bump\n\nRelease 0.2")
        self.git("tag", "braidworks-core-v0.2.0")
        text = changelog.notes(self.root, "braidworks-core-v0.2.0")
        self.assertTrue(text.startswith("- Release 0.2 (#4)"))
        self.assertIn("compare/braidworks-core-v0.1.0...braidworks-core-v0.2.0", text)


if __name__ == "__main__":
    unittest.main()
