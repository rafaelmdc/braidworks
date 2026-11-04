"""The link checker must catch missing pages and anchors, and ignore code and URLs."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_links
from check_links import check_file, slug


class LinkCheckTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.addCleanup(setattr, check_links, "ROOT", check_links.ROOT)
        check_links.ROOT = self.root
        check_links.anchors.cache_clear()
        (self.root / "how-to").mkdir()
        (self.root / "how-to" / "install.md").write_text(
            "# Install\n\n## Start the browser\n\n## Start the browser\n"
        )

    def page(self, text: str) -> Path:
        path = self.root / "index.md"
        path.write_text(text)
        return path

    def test_valid_links_pass(self):
        page = self.page(
            "[a](how-to/install.md) [b](how-to/install.md#start-the-browser) "
            "[c](how-to/install.md#start-the-browser-1) [d](how-to/) [e](#top)\n# Top\n"
            "[web](https://example.org/x.md) [mail](mailto:a@b.c)\n"
            "```\n[ignored](missing.md)\n```\n"
        )
        self.assertEqual(check_file(page), [])

    def test_missing_file_and_anchor_are_reported(self):
        page = self.page("[a](how-to/gone.md)\n[b](how-to/install.md#add-the-browser)\n")
        problems = check_file(page)
        self.assertEqual(len(problems), 2)
        self.assertIn("index.md:1: missing target how-to/gone.md", problems[0])
        self.assertIn("index.md:2: no heading for #add-the-browser", problems[1])

    def test_slug_matches_github(self):
        self.assertEqual(slug("Query from Python"), "query-from-python")
        self.assertEqual(slug("`get` and `Session`"), "get-and-session")
        self.assertEqual(slug("Check coverage & export"), "check-coverage--export")


if __name__ == "__main__":
    unittest.main()
